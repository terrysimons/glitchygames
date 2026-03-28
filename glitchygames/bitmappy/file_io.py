"""File I/O operations for the Bitmappy editor.

Handles drag-and-drop file loading, PNG-to-TOML conversion, and sprite loading
into the canvas. Extracted from BitmapEditorScene to reduce class complexity.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pygame

from glitchygames.color import (
    ALPHA_TRANSPARENCY_THRESHOLD,
    RGBA_COMPONENT_COUNT,
)
from glitchygames.sprites.animated import SpriteFrame

from .models import MockEvent
from .toml_processing import (
    build_color_to_glyph_mapping,
    generate_pixel_string,
    generate_toml_content,
    quantize_colors_if_needed,
)

if TYPE_CHECKING:
    import numpy as np

    from glitchygames import events
    from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

    from .animated_canvas import AnimatedCanvasSprite
    from .protocols import EditorContext


class FileIOManager:
    """Manages file I/O operations for the Bitmappy editor.

    Handles drag-and-drop file events, PNG-to-TOML conversion, and loading
    sprites into the editor canvas. Operates on editor state via the editor
    reference passed at construction time.
    """

    def __init__(self, editor: EditorContext) -> None:
        """Initialize the FileIOManager.

        Args:
            editor: The editor context providing access to shared state.

        """
        self.editor = editor
        self.log = logging.getLogger('game.tools.bitmappy.file_io')
        self.log.addHandler(logging.NullHandler())

    # ──────────────────────────────────────────────────────────────────────
    # Drop event handling
    # ──────────────────────────────────────────────────────────────────────

    def on_drop_file_event(self, event: events.HashableEvent) -> None:
        """Handle drop file event.

        Args:
            event: The pygame event containing the dropped file information.

        """
        # Get the file path from the event
        file_path = event.file
        self.log.info('File dropped: %s', file_path)

        # Get file size
        try:
            file_size = Path(file_path).stat().st_size
            self.log.info('File size: %s bytes', file_size)
        except OSError:
            self.log.exception('Could not get file size')
            return

        # First, check if any film strip sprites can handle the drop
        if self._try_film_strip_drop(event):
            return

        # If no film strip handled it, check if drop is on the canvas
        self._try_canvas_drop(file_path)

    def _try_film_strip_drop(self, event: events.HashableEvent) -> bool:
        """Try to handle a file drop via film strip sprites.

        Args:
            event: The pygame event containing the dropped file information.

        Returns:
            True if a film strip handled the drop, False otherwise.

        """
        if not hasattr(self.editor, 'film_strip_sprites') or not self.editor.film_strip_sprites:
            return False

        for strip_name, film_strip_sprite in self.editor.film_strip_sprites.items():
            if not hasattr(film_strip_sprite, 'on_drop_file_event'):
                continue
            try:
                if film_strip_sprite.on_drop_file_event(event):
                    self.log.info("Film strip '%s' handled the drop", strip_name)
                    return True
            except AttributeError, TypeError, ValueError, OSError, pygame.error:
                self.log.exception('Error in film strip drop handler')
                continue
        return False

    def _try_canvas_drop(self, file_path: str) -> None:
        """Try to handle a file drop on the canvas.

        Args:
            file_path: Path to the dropped file.

        """
        # Get current mouse position since drop events don't include position
        mouse_pos = pygame.mouse.get_pos()
        if not (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.editor.canvas.rect is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.editor.canvas.rect.collidepoint(mouse_pos)
        ):
            self.log.info('Drop not on canvas or film strip - ignoring drop at %s', mouse_pos)
            return

        self.log.info('Drop detected on canvas at %s', mouse_pos)
        if file_path.lower().endswith('.png'):
            self.log.info('PNG file detected - converting to bitmappy format')
            converted_toml_path = self._convert_png_to_bitmappy(file_path)
            if converted_toml_path:
                # Auto-load the converted TOML file
                self._load_converted_sprite(converted_toml_path)
            else:
                self.log.error('Failed to convert PNG to bitmappy format')
        elif file_path.lower().endswith('.toml'):
            self.log.info('TOML file detected - loading directly')
            # Load the TOML file directly
            self._load_converted_sprite(file_path)
        else:
            self.log.info('Unsupported file type dropped on canvas: %s', file_path)

    # ──────────────────────────────────────────────────────────────────────
    # PNG-to-TOML conversion pipeline
    # ──────────────────────────────────────────────────────────────────────

    def _convert_png_to_bitmappy(self, file_path: str) -> str | None:
        """Convert a PNG file to bitmappy TOML format.

        Args:
            file_path: Path to the PNG file to convert.

        Returns:
            Path to the converted TOML file, or None if conversion failed.

        """
        try:
            image, width, height = self._load_and_resize_png(file_path)
            pixel_array: Any = pygame.surfarray.array3d(image)  # type: ignore[reportUnknownMemberType]
            self.log.info(f'Pixel array shape: {pixel_array.shape}')

            has_transparency, original_image = self._detect_png_transparency(image, file_path)
            unique_colors, sample_count, transparent_pixels = self._sample_png_colors(
                pixel_array,
                width,
                height,
                has_transparency=has_transparency,
                original_image=original_image,
            )

            if has_transparency:
                self.log.info(
                    'Found %s transparent pixels, mapped to magenta (255, 0, 255)',
                    transparent_pixels,
                )
            self.log.info(
                f'Sampled {sample_count} pixels, found {len(unique_colors)} unique colors',
            )

            unique_colors = quantize_colors_if_needed(
                unique_colors,
                has_transparency=has_transparency,
                log=self.log,
            )
            color_mapping = build_color_to_glyph_mapping(
                unique_colors,
                has_transparency=has_transparency,
                log=self.log,
            )

            pixel_string = generate_pixel_string(
                pixel_array,
                width,
                height,
                has_transparency=has_transparency,
                original_image=original_image,
                color_mapping=color_mapping,
                log=self.log,
            )

            toml_content = generate_toml_content(
                file_path,
                pixel_string,
                color_mapping,
                log=self.log,
            )
            output_path = self._save_and_validate_toml(file_path, toml_content)

            self.log.info('Successfully converted PNG to bitmappy format: %s', output_path)
            return str(output_path)

        except OSError, ValueError, TypeError, AttributeError, pygame.error:
            self.log.exception('Error converting PNG to bitmappy format')
            return None

    def _load_and_resize_png(self, file_path: str) -> tuple[pygame.Surface, int, int]:
        """Load a PNG image and resize it to match the canvas size.

        Args:
            file_path: Path to the PNG file.

        Returns:
            Tuple of (image surface, width, height).

        """
        self.log.info('Loading PNG image: %s', file_path)
        image = pygame.image.load(file_path)
        width, height = image.get_size()
        self.log.info('Image dimensions: %sx%s', width, height)

        # Get current canvas size for resizing
        canvas_width, canvas_height = 32, 32  # Default fallback
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            canvas_width = self.editor.canvas.pixels_across
            canvas_height = self.editor.canvas.pixels_tall
            self.log.info('Using current canvas size: %sx%s', canvas_width, canvas_height)
        else:
            self.log.info('No canvas found, using default size: 32x32')

        # Check if image needs resizing to match canvas size
        if width != canvas_width or height != canvas_height:
            self.log.info(
                'Resizing image from %sx%s to %sx%s to match canvas',
                width,
                height,
                canvas_width,
                canvas_height,
            )
            image = pygame.transform.scale(image, (canvas_width, canvas_height))
            width, height = canvas_width, canvas_height
            self.log.info('Resized image to %sx%s', width, height)

        # Convert to RGB if needed, handling transparency
        if image.get_flags() & pygame.SRCALPHA:
            rgb_image = pygame.Surface((width, height))
            rgb_image.fill((255, 255, 255))  # White background
            rgb_image.blit(image, (0, 0))
            image = rgb_image
            self.log.info('Converted image with alpha channel to RGB')

        return image, width, height

    def _detect_png_transparency(
        self,
        image: pygame.Surface,
        file_path: str,
    ) -> tuple[bool, pygame.Surface | None]:
        """Detect whether the original PNG image has transparency.

        Args:
            image: The converted RGB image surface.
            file_path: Path to the original PNG file.

        Returns:
            Tuple of (has_transparency, original_image_with_alpha_or_None).

        """
        if not (image.get_flags() & pygame.SRCALPHA):
            return False, None

        original_image = pygame.image.load(file_path)
        if original_image.get_flags() & pygame.SRCALPHA:
            self.log.info(
                'Image has transparency - will map transparent pixels to magenta (255, 0, 255)',
            )
            return True, original_image
        return False, None

    def _sample_png_colors(
        self,
        pixel_array: np.ndarray[Any, Any],
        width: int,
        height: int,
        *,
        has_transparency: bool,
        original_image: pygame.Surface | None,
    ) -> tuple[set[tuple[int, int, int]], int, int]:
        """Sample pixels from the image to find unique colors.

        Args:
            pixel_array: The numpy pixel array from the image.
            width: Image width.
            height: Image height.
            has_transparency: Whether the image has transparency.
            original_image: The original image with alpha channel, or None.

        Returns:
            Tuple of (unique_colors set, sample_count, transparent_pixel_count).

        """
        # Use a more efficient approach for large images
        sample_step = max(1, (width * height) // 10000)  # Sample up to 10k pixels
        self.log.info('Sampling every %s pixels for color analysis', sample_step)

        unique_colors: set[tuple[int, int, int]] = set()
        sample_count = 0
        transparent_pixels = 0

        for y in range(0, height, sample_step):
            for x in range(0, width, sample_step):
                r, g, b = pixel_array[x, y]
                # Ensure we're working with Python ints, not numpy types
                color = (int(r), int(g), int(b))
                unique_colors.add(color)
                sample_count += 1

                # Check for transparency if we have the original image
                if has_transparency and original_image is not None:
                    original_pixel = original_image.get_at((x, y))
                    if original_pixel.a < ALPHA_TRANSPARENCY_THRESHOLD:
                        transparent_pixels += 1
                        # Map transparent pixels to magenta
                        unique_colors.discard(color)
                        unique_colors.add((255, 0, 255))

        return unique_colors, sample_count, transparent_pixels

    # ──────────────────────────────────────────────────────────────────────
    # TOML saving and validation
    # ──────────────────────────────────────────────────────────────────────

    def _save_and_validate_toml(self, file_path: str, toml_content: str) -> Path:
        """Save the TOML content to a file and validate its structure.

        Args:
            file_path: Original PNG file path (used to derive output path).
            toml_content: The complete TOML content string.

        Returns:
            The output path of the saved TOML file.

        """
        output_path = Path(file_path).with_suffix('.toml')
        Path(output_path).write_text(toml_content, encoding='utf-8')

        self.log.info('Validating generated TOML file...')
        self._validate_toml_content(output_path)

        return output_path

    def _validate_toml_content(self, output_path: Path) -> None:
        """Validate that a generated TOML file has required sections.

        Args:
            output_path: Path to the TOML file to validate.

        Raises:
            ValueError: If the TOML file is missing required sections.

        """
        with output_path.open(encoding='utf-8') as f:
            content = f.read()

        if '[sprite]' not in content:
            self.log.error('TOML file missing [sprite] section!')
            msg = 'Generated TOML file has no [sprite] section'
            raise ValueError(msg)

        if '[colors]' not in content:
            self.log.error('TOML file missing [colors] section!')
            msg = 'Generated TOML file has no [colors] section'
            raise ValueError(msg)

        color_count = content.count('[colors."')
        if color_count == 0:
            self.log.error('TOML file has no color definitions!')
            msg = 'Generated TOML file has no color definitions'
            raise ValueError(msg)

        self.log.info('TOML validation passed: %s colors defined', color_count)

    # ──────────────────────────────────────────────────────────────────────
    # Sprite loading into canvas
    # ──────────────────────────────────────────────────────────────────────

    def _load_converted_sprite(self, toml_path: str) -> None:
        """Load a converted TOML sprite into the editor.

        Args:
            toml_path: Path to the converted TOML file.

        """
        try:
            self.log.info('=== STARTING _load_converted_sprite ===')
            canvas_sprite = self._find_canvas_sprite()

            if not canvas_sprite:
                self.log.warning('Could not find canvas sprite to load converted file')
                return

            self._load_sprite_into_canvas(canvas_sprite, toml_path)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
            self._transfer_loaded_sprite_pixels(canvas_sprite)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
            self._finalize_sprite_load(canvas_sprite)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]

        except (
            OSError,
            ValueError,
            AttributeError,
            TypeError,
            KeyError,
            pygame.error,
        ):
            self.log.exception('Error loading converted sprite into editor')

    def _find_canvas_sprite(self) -> object | None:
        """Find the canvas sprite in the scene that can handle file loading.

        Returns:
            The canvas sprite if found, or None.

        """
        all_sprites: list[Any] = list(self.editor.all_sprites)
        self.log.info(f'Searching for canvas sprite in {len(all_sprites)} sprites...')
        for i, sprite in enumerate(all_sprites):
            self.log.info(
                f'Sprite {i}: {type(sprite)} - has on_load_file_event:'
                f' {hasattr(sprite, "on_load_file_event")}',
            )
            if hasattr(sprite, 'on_load_file_event'):
                self.log.info(f'Found canvas sprite: {type(sprite)}')
                return sprite
        return None

    def _load_sprite_into_canvas(self, canvas_sprite: AnimatedCanvasSprite, toml_path: str) -> None:
        """Load a TOML sprite file into the canvas sprite.

        Args:
            canvas_sprite: The canvas sprite to load into.
            toml_path: Path to the TOML file.

        """
        self.log.info('Loading converted sprite: %s', toml_path)
        self.log.info(f'Found canvas sprite: {type(canvas_sprite)}')

        # Create a mock event for loading
        mock_event = MockEvent(text=toml_path)
        self.log.info('Calling on_load_file_event...')
        canvas_sprite.on_load_file_event(mock_event)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
        self.log.info('on_load_file_event completed')

        # Update border thickness after loading (in case canvas was resized)
        self.log.info('Updating border thickness after sprite load...')
        canvas_sprite._update_border_thickness()  # type: ignore[reportPrivateUsage]

        # Force a complete redraw to apply the new border settings
        self.log.info('Forcing canvas redraw with new border settings...')
        canvas_sprite.force_redraw()

    def _transfer_loaded_sprite_pixels(self, canvas_sprite: AnimatedCanvasSprite) -> None:
        """Transfer pixel data from a loaded animated sprite to the canvas.

        Args:
            canvas_sprite: The canvas sprite containing the loaded animation.

        """
        self.log.info(f'Canvas sprite type: {type(canvas_sprite)}')
        self.log.info(
            f'Canvas sprite has animated_sprite: {hasattr(canvas_sprite, "animated_sprite")}',
        )
        if hasattr(canvas_sprite, 'animated_sprite'):
            self.log.info(f'animated_sprite value: {canvas_sprite.animated_sprite}')
        if not (hasattr(canvas_sprite, 'animated_sprite') and canvas_sprite.animated_sprite):
            return

        self.log.info(f'Animated sprite loaded: {canvas_sprite.animated_sprite}')
        if not hasattr(canvas_sprite.animated_sprite, '_animations'):
            return

        animations = list(canvas_sprite.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        self.log.info('Animations: %s', animations)
        if not animations:
            return

        first_anim = animations[0]
        frames = canvas_sprite.animated_sprite._animations[first_anim]  # type: ignore[reportPrivateUsage]
        self.log.info(f"First animation '{first_anim}' has {len(frames)} frames")
        if not frames:
            return

        first_frame = frames[0]
        self.log.info(f'First frame size: {first_frame.get_size()}')
        self._apply_frame_pixels_to_canvas(canvas_sprite, first_frame)

    def _apply_frame_pixels_to_canvas(
        self,
        canvas_sprite: AnimatedCanvasSprite,
        first_frame: SpriteFrame,
    ) -> None:
        """Apply pixel data from a frame to the canvas.

        Args:
            canvas_sprite: The canvas sprite to update.
            first_frame: The first frame of the animation to extract pixels from.

        """
        self.log.info('Transferring pixel data from loaded sprite to canvas...')
        if not (hasattr(first_frame, 'image') and first_frame.image):
            return

        frame_surface = first_frame.image
        frame_width, frame_height = frame_surface.get_size()
        self.log.info('Frame surface size: %sx%s', frame_width, frame_height)

        # Convert the frame surface to pixel data
        pixel_data: list[tuple[int, ...]] = []
        for y in range(frame_height):
            for x in range(frame_width):
                color = frame_surface.get_at((x, y))
                # Handle transparency key specially - keep it opaque for canvas
                if len(color) == RGBA_COMPONENT_COUNT:
                    r, g, b, a = color
                    if (r, g, b) == (255, 0, 255) and a == 0:
                        # Transparent magenta should be opaque magenta for canvas
                        pixel_data.append((255, 0, 255, 255))
                    else:
                        pixel_data.append((r, g, b, a))
                else:
                    pixel_data.append((color.r, color.g, color.b, 255))

        # Update canvas pixels
        canvas_sprite.pixels = pixel_data
        canvas_sprite.dirty_pixels = [True] * len(pixel_data)
        self.log.info(f'Transferred {len(pixel_data)} pixels to canvas')

        # Update mini view pixels too
        if hasattr(canvas_sprite, 'mini_view') and canvas_sprite.mini_view is not None:
            canvas_sprite.mini_view.pixels = pixel_data.copy()
            canvas_sprite.mini_view.dirty_pixels = [True] * len(pixel_data)
            self.log.info('Updated mini view pixels')

    def _finalize_sprite_load(self, canvas_sprite: AnimatedCanvasSprite) -> None:
        """Finalize sprite loading by forcing redraws and initializing onion skinning.

        Args:
            canvas_sprite: The canvas sprite that was loaded.

        """
        # Force canvas redraw to show the new sprite
        self.log.info('Forcing canvas redraw after loading...')
        canvas_sprite.dirty = 1
        canvas_sprite.force_redraw()

        # Update mini view if it exists
        if hasattr(canvas_sprite, 'mini_view') and canvas_sprite.mini_view is not None:
            self.log.info('Updating mini view...')
            canvas_sprite.mini_view.pixels = canvas_sprite.pixels.copy()
            canvas_sprite.mini_view.dirty_pixels = [True] * len(canvas_sprite.pixels)
            canvas_sprite.mini_view.dirty = 1
            canvas_sprite.mini_view.force_redraw()

        # Initialize onion skinning for the loaded sprite
        if hasattr(canvas_sprite, 'animated_sprite') and canvas_sprite.animated_sprite:
            self._initialize_onion_skinning_for_sprite(canvas_sprite.animated_sprite)

        self.log.info('Converted sprite loaded successfully into editor')

    def _initialize_onion_skinning_for_sprite(self, loaded_sprite: AnimatedSprite) -> None:
        """Initialize onion skinning for a newly loaded sprite.

        Args:
            loaded_sprite: The loaded animated sprite

        """
        try:
            from .onion_skinning import get_onion_skinning_manager

            onion_manager = get_onion_skinning_manager()

            # Clear any existing onion skinning state for this sprite
            if hasattr(loaded_sprite, '_animations') and loaded_sprite._animations:  # type: ignore[reportPrivateUsage]
                for animation_name in loaded_sprite._animations:  # type: ignore[reportPrivateUsage]
                    onion_manager.clear_animation_onion_skinning(animation_name)
                    self.log.debug('Cleared onion skinning state for animation: %s', animation_name)

            # Initialize onion skinning for all animations in the loaded sprite
            if hasattr(loaded_sprite, '_animations') and loaded_sprite._animations:  # type: ignore[reportPrivateUsage]
                for animation_name, frames in loaded_sprite._animations.items():  # type: ignore[reportPrivateUsage]
                    # Enable onion skinning for all frames except the first one
                    frame_states = {}
                    for frame_idx in range(len(frames)):
                        # Enable onion skinning for all frames except frame 0
                        frame_states[frame_idx] = frame_idx != 0

                    onion_manager.set_animation_onion_state(animation_name, frame_states)  # type: ignore[arg-type]
                    self.log.debug(
                        f"Initialized onion skinning for animation '{animation_name}' with"
                        f' {len(frames)} frames',
                    )

            # Ensure global onion skinning is enabled
            if not onion_manager.is_global_onion_skinning_enabled():
                onion_manager.toggle_global_onion_skinning()
                self.log.debug('Enabled global onion skinning for new sprite')

            self.log.info('Onion skinning initialized for loaded sprite')

        except ImportError, AttributeError, KeyError, TypeError:
            self.log.exception('Failed to initialize onion skinning for loaded sprite')
