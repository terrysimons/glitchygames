"""Editor setup delegate -- initialization helpers for BitmapEditorScene.

This module contains all setup methods and their helpers that are
exclusively called during ``__init__`` of ``BitmapEditorScene``.  Extracting
them into a composition delegate keeps the main editor module focused on
runtime behaviour (event handling, update/render loop, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pygame

# Try to import voice recognition, but don't fail if it's not available
try:
    from glitchygames.events.voice import VoiceEventManager
except ImportError:
    VoiceEventManager = None  # ty: ignore[invalid-assignment]

from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.ui import (
    MenuBar,
    MenuItem,
    MultiLineTextBox,
    TextSprite,
)

from .animated_canvas import AnimatedCanvasSprite
from .constants import (
    LOG,
    MAGENTA_TRANSPARENT,
    MIN_FILM_STRIPS_FOR_PANEL_POSITIONING,
    MIN_PIXEL_DISPLAY_SIZE,
)
from .history.operations import (
    CanvasOperationTracker,
    ControllerPositionOperationTracker,
    CrossAreaOperationTracker,
    FilmStripOperationTracker,
)
from .history.undo_redo import UndoRedoManager
from .utils import resource_path

if TYPE_CHECKING:
    from glitchygames.bitmappy.editor import BitmapEditorScene


class EditorSetup:
    """Delegate providing all setup helpers used during editor initialisation.

    These methods are called from ``BitmapEditorScene.__init__`` and should
    **not** be called at runtime.  The delegate receives a reference to the
    editor instance so it can set attributes on it directly.
    """

    def __init__(self, editor: BitmapEditorScene) -> None:
        """Initialize the editor setup delegate.

        Args:
            editor: The BitmapEditorScene instance to set up.

        """
        self.editor = editor

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def setup_menu_bar(self) -> None:
        """Set up the menu bar and menu items."""
        menu_bar_height = 24  # Taller menu bar

        # Different heights for icon vs text items
        icon_height = 16  # Smaller height for icon
        menu_item_height = menu_bar_height  # Full height for text items

        # Different vertical offsets for icon vs text
        icon_y = (menu_bar_height - icon_height) // 2 - 2  # Center the icon and move up 2px
        menu_item_y = 0  # Text items use full height

        # Create the menu bar using the UI library's MenuBar
        self.editor.menu_bar = MenuBar(
            name='Menu Bar',
            x=0,
            y=0,
            width=self.editor.screen_width,
            height=menu_bar_height,
            groups=self.editor.all_sprites,
        )

        # Add the raspberry icon with its specific height
        icon_path = resource_path('glitchygames', 'assets', 'raspberry.toml')
        self.editor.menu_icon = MenuItem(
            name=None,
            x=4,  # Add 4px offset from left edge
            y=icon_y,
            width=16,
            height=icon_height,  # Use icon-specific height
            filename=str(icon_path),
            groups=self.editor.all_sprites,
        )
        self.editor.menu_bar.add_menu(self.editor.menu_icon)

        # Add all menus with full height
        menu_item_x = 0  # Start at left edge
        icon_width = 16  # Width of the raspberry icon
        menu_spacing = 2  # Reduced spacing between items
        menu_item_width = 48
        border_offset = self.editor.menu_bar.border_width  # Usually 2px

        # Start after icon, compensating for border
        menu_item_x = (icon_width + menu_spacing) - border_offset

        new_menu = MenuItem(
            name='New',
            x=menu_item_x,
            y=menu_item_y - border_offset,  # Compensate for y border too
            width=menu_item_width,
            height=menu_item_height,
            groups=self.editor.all_sprites,
        )
        self.editor.menu_bar.add_menu(new_menu)

        # Move to next position
        menu_item_x += menu_item_width + menu_spacing

        save_menu = MenuItem(
            name='Save',
            x=menu_item_x,
            y=menu_item_y - border_offset,
            width=menu_item_width,
            height=menu_item_height,
            groups=self.editor.all_sprites,
        )
        self.editor.menu_bar.add_menu(save_menu)

        # Move to next position
        menu_item_x += menu_item_width + menu_spacing

        load_menu = MenuItem(
            name='Load',
            x=menu_item_x,
            y=menu_item_y - border_offset,
            width=menu_item_width,
            height=menu_item_height,
            groups=self.editor.all_sprites,
        )
        self.editor.menu_bar.add_menu(load_menu)

    # ------------------------------------------------------------------
    # Canvas setup and helpers
    # ------------------------------------------------------------------

    def setup_canvas(self, options: dict[str, Any]) -> None:
        """Set up the canvas sprite."""
        # Calculate canvas dimensions and pixel size
        pixels_across, pixels_tall, pixel_size = self._calculate_canvas_dimensions(options)

        # Create animated sprite with single frame
        animated_sprite = self._create_animated_sprite(pixels_across, pixels_tall)

        # Store the animated sprite as the shared instance
        self.editor.animated_sprite = animated_sprite

        # Create the main canvas sprite
        self._create_canvas_sprite(animated_sprite, pixels_across, pixels_tall, pixel_size)

        # Finalize setup and start animation
        self._finalize_canvas_setup(animated_sprite, options)

    def _calculate_canvas_dimensions(
        self,
        options: dict[str, Any],
    ) -> tuple[int, int, int]:
        """Calculate canvas dimensions and pixel size.

        Args:
            options: Dictionary containing canvas configuration

        Returns:
            Tuple of (pixels_across, pixels_tall, pixel_size)

        """
        menu_bar_height = 24
        bottom_margin = 80  # Space needed for sliders and color well
        available_height = (
            self.editor.screen_height - bottom_margin - menu_bar_height
        )  # Use menu_bar_height instead of 32

        # Calculate pixel size to fit the canvas in the available space
        width, height = options['size'].split('x')
        pixels_across = int(width)
        pixels_tall = int(height)

        # ===== DEBUG: INITIAL CANVAS SIZING =====
        LOG.debug('===== DEBUG: INITIAL CANVAS SIZING =====')
        LOG.debug(
            f'Screen: {self.editor.screen_width}x{self.editor.screen_height}, Sprite:'
            f' {pixels_across}x{pixels_tall}',
        )
        LOG.debug(f'Available height: {available_height}')
        LOG.debug(f'Height constraint: {available_height // pixels_tall}')
        LOG.debug(f'Width constraint: {(self.editor.screen_width * 1 // 2) // pixels_across}')
        LOG.debug(f'350px width constraint: {350 // pixels_across}')
        LOG.debug(f'320x320 constraint: {320 // max(pixels_across, pixels_tall)}')

        # Calculate pixel size based on available space
        pixel_size = min(
            available_height // pixels_tall,  # Height-based size
            # Width-based size (use 1/2 of screen width)
            (self.editor.screen_width * 1 // 2) // pixels_across,
            # Maximum width constraint: 350px
            350 // pixels_across,
        )
        LOG.debug(f'Calculated pixel_size: {pixel_size}')

        # For very large sprites, ensure we get at least 2x2 pixel size
        if pixel_size < MIN_PIXEL_DISPLAY_SIZE:
            pixel_size = (
                MIN_PIXEL_DISPLAY_SIZE  # Force minimum 2x2 pixel size for very large sprites
            )
            LOG.debug('*** FORCING minimum 2x2 pixel size for large sprite ***')

        LOG.debug(f'Final pixel_size: {pixel_size}')
        LOG.debug(f'Canvas will be: {pixels_across * pixel_size}x{pixels_tall * pixel_size}')
        LOG.debug('===== END DEBUG =====\n')
        # Ensure minimum pixel size of 1x1
        pixel_size = max(pixel_size, 1)

        return pixels_across, pixels_tall, pixel_size

    @staticmethod
    def _create_animated_sprite(pixels_across: int, pixels_tall: int) -> AnimatedSprite:
        """Create animated sprite with single frame.

        Args:
            pixels_across: Number of pixels across the canvas
            pixels_tall: Number of pixels tall the canvas

        Returns:
            Configured AnimatedSprite instance

        """
        # Create single test frame with SRCALPHA for per-pixel alpha support
        surface1 = pygame.Surface((pixels_across, pixels_tall), pygame.SRCALPHA)
        surface1.fill(MAGENTA_TRANSPARENT)  # Magenta frame (transparent)
        frame1 = SpriteFrame(surface1)
        frame1.pixels = [MAGENTA_TRANSPARENT] * (pixels_across * pixels_tall)  # ty: ignore[invalid-assignment]

        # DEBUG: Log the first frame's pixel data
        LOG.info(f'DEBUG: First frame initialized with {len(frame1.pixels)} pixels')
        LOG.info(f'DEBUG: First few pixels: {frame1.pixels[:5]}')
        LOG.info(f'DEBUG: All pixels same color: {len(set(frame1.pixels)) == 1}')

        # Create animated sprite using proper initialization - single frame
        animated_sprite = AnimatedSprite()
        # Use the proper method to set up animations with single frame
        animation_name = 'strip_1'  # Use a generic name for new sprites
        animated_sprite._animations = {animation_name: [frame1]}  # type: ignore[reportPrivateUsage]
        animated_sprite._frame_interval = 0.5  # type: ignore[reportPrivateUsage]
        animated_sprite._is_looping = True  # type: ignore[reportPrivateUsage]  # Enable looping for the animation

        # Set up the frame manager properly
        animated_sprite.frame_manager.current_animation = animation_name
        animated_sprite.frame_manager.current_frame = 0

        # Initialize the sprite properly like a loaded sprite would be
        animated_sprite._update_surface_and_mark_dirty()  # type: ignore[reportPrivateUsage]

        # Start in a paused state initially
        animated_sprite.pause()

        return animated_sprite

    def _create_canvas_sprite(
        self,
        animated_sprite: AnimatedSprite,
        pixels_across: int,
        pixels_tall: int,
        pixel_size: int,
    ) -> None:
        """Create the main animated canvas sprite.

        Args:
            animated_sprite: The animated sprite to use
            pixels_across: Number of pixels across the canvas
            pixels_tall: Number of pixels tall the canvas
            pixel_size: Size of each pixel in screen coordinates

        """
        menu_bar_height = 24

        # Create the animated canvas with the calculated pixel dimensions
        self.editor.canvas = AnimatedCanvasSprite(
            animated_sprite=animated_sprite,
            name='Animated Bitmap Canvas',
            x=0,
            y=menu_bar_height,  # Position canvas right below menu bar
            pixels_across=pixels_across,
            pixels_tall=pixels_tall,
            pixel_width=pixel_size,
            pixel_height=pixel_size,
            groups=self.editor.all_sprites,
        )

        # Set parent scene reference for canvas
        self.editor.canvas.parent_scene = self.editor

        # Debug: Log canvas position and size
        self.editor.log.info(
            'AnimatedCanvasSprite created at position '
            f'({self.editor.canvas.rect.x}, {self.editor.canvas.rect.y}) '
            f'with size {self.editor.canvas.rect.size}',
        )
        self.editor.log.info(f'AnimatedCanvasSprite groups: {self.editor.canvas.groups}')
        self.editor.log.info(f'AnimatedCanvasSprite dirty: {self.editor.canvas.dirty}')

    @staticmethod
    def _finalize_canvas_setup(animated_sprite: AnimatedSprite, options: dict[str, Any]) -> None:
        """Finalize canvas setup and start animation.

        Args:
            animated_sprite: The animated sprite to finalize
            options: Dictionary containing canvas configuration

        """
        # Start the animation after everything is set up
        animated_sprite.play()

        size_str = options.get('size')
        assert size_str is not None
        width, height = size_str.split('x')
        AnimatedCanvasSprite.WIDTH = int(width)  # ty: ignore[unresolved-attribute]
        AnimatedCanvasSprite.HEIGHT = int(height)  # ty: ignore[unresolved-attribute]

    # ------------------------------------------------------------------
    # Debug text box / AI label
    # ------------------------------------------------------------------

    def setup_debug_text_box(self) -> None:
        """Set up the debug text box and AI label."""
        # Calculate debug text box position and size - align to bottom right corner
        debug_height = 186  # Fixed height for AI chat box

        # Calculate film strip left x position (should be less than color well's right x - 1)
        if hasattr(self.editor, 'color_well') and self.editor.color_well:
            film_strip_left_x = (
                self.editor.color_well.rect.right + 1
            )  # Film strip left x = color well right x + 1
        else:
            # Fallback if color well not available
            film_strip_left_x = self.editor.screen_width - 200

        # AI sprite box should be clamped to right side of screen and grow left
        # but not grow left more than the film strip left x
        debug_x = film_strip_left_x  # Start from film strip left x
        debug_width = self.editor.screen_width - debug_x  # Extend to right edge of screen

        # Position below the 2nd film strip if it exists, otherwise clamp to bottom of screen
        if (
            hasattr(self.editor, 'film_strips')
            and self.editor.film_strips
            and len(self.editor.film_strips) >= MIN_FILM_STRIPS_FOR_PANEL_POSITIONING
        ):
            # Find the bottom of the 2nd film strip
            second_strip_bottom = 0
            # Safely get the second film strip to handle race conditions during sprite loading
            try:
                # Convert to list to safely access by index
                film_strip_list = list(self.editor.film_strips.values())
                if len(film_strip_list) >= MIN_FILM_STRIPS_FOR_PANEL_POSITIONING and hasattr(
                    film_strip_list[1],
                    'rect',
                ):
                    second_strip_bottom = film_strip_list[1].rect.bottom
            except IndexError, KeyError, AttributeError:
                # Handle race condition where film strips are in transition
                second_strip_bottom = 0
            debug_y = second_strip_bottom + 30  # 30 pixels below the 2nd strip
            # Ensure it doesn't go above the bottom of the screen
            debug_y = min(debug_y, self.editor.screen_height - debug_height)
        else:
            # Fallback: clamp to bottom of screen
            debug_y = self.editor.screen_height - debug_height

        # Create the AI label
        label_height = 20
        self.editor.ai_label = TextSprite(
            x=int(debug_x),
            y=debug_y - label_height,  # Position above the text box
            width=int(debug_width),
            height=label_height,
            text='AI Sprite',
            text_color=(255, 255, 255),  # White text
            background_color=(0, 0, 0),  # Solid black background like color well
            groups=self.editor.all_sprites,
        )

        # Create the debug text box
        self.editor.debug_text = MultiLineTextBox(
            name='Debug Output',
            x=int(debug_x),
            y=debug_y,
            width=int(debug_width),
            height=debug_height,
            text='',  # Changed to empty string
            parent=self.editor,  # Pass self as parent
            groups=self.editor.all_sprites,
        )

    # ------------------------------------------------------------------
    # Voice recognition
    # ------------------------------------------------------------------

    def setup_voice_recognition(self) -> None:
        """Set up voice recognition for voice commands.

        **STATUS: DISABLED BY DEFAULT**

        This functionality is implemented but currently disabled in the setup() method
        (see line 6413-6414). Voice recognition requires:
        - A microphone to be connected and available
        - The glitchygames.events.voice module to be importable
        - Proper audio system configuration

        **Why Disabled:**
        - Voice recognition can be unreliable across different systems
        - Requires user permission for microphone access
        - May impact performance or cause issues on some platforms
        - Currently considered experimental/incomplete

        **Current Implementation:**
        When enabled, this method registers the following voice commands:
        - "clear the ai sprite box"
        - "clear ai sprite box"
        - "clear ai box"
        - "clear the ai sprite"
        - "clear ai sprite"
        - "clear the ai sprite window"
        - "clear ai sprite window"

        All commands trigger the clear_ai_sprite_box() callback.

        **To Enable:**
        1. Uncomment the call to setup_voice_recognition() in __init__
        2. Ensure VoiceEventManager is available (imports at lines 37-41)
        3. Test microphone access and speech recognition accuracy
        4. Verify no performance issues or crashes

        **Future Plans:**
        - Expand voice command vocabulary for more sprite editing operations
        - Add voice feedback/confirmation for commands
        - Integrate with scene manager for better coordination
        - Add configuration options for voice recognition sensitivity

        **Cleanup:**
        Always call _cleanup_voice_recognition() during scene teardown to properly
        release microphone resources and stop background threads.

        """
        try:
            if VoiceEventManager is None:
                self.editor.log.info('Voice recognition not available')
                self.editor.voice_manager = None
                return
            self.editor.voice_manager = VoiceEventManager(logger=self.editor.log)

            if self.editor.voice_manager.is_available():
                # Register voice commands
                self.editor.voice_manager.register_command(
                    'clear the ai sprite box',
                    self.editor.clear_ai_sprite_box,
                )
                self.editor.voice_manager.register_command(
                    'clear ai sprite box',
                    self.editor.clear_ai_sprite_box,
                )
                self.editor.voice_manager.register_command(
                    'clear ai box',
                    self.editor.clear_ai_sprite_box,
                )
                # Add commands for what speech recognition actually hears
                self.editor.voice_manager.register_command(
                    'clear the ai sprite',
                    self.editor.clear_ai_sprite_box,
                )
                self.editor.voice_manager.register_command(
                    'clear ai sprite',
                    self.editor.clear_ai_sprite_box,
                )
                # Add command for "window" variation
                self.editor.voice_manager.register_command(
                    'clear the ai sprite window',
                    self.editor.clear_ai_sprite_box,
                )
                self.editor.voice_manager.register_command(
                    'clear ai sprite window',
                    self.editor.clear_ai_sprite_box,
                )

                # Start listening for voice commands
                self.editor.voice_manager.start_listening()
                self.editor.log.info('Voice recognition initialized and started')
            else:
                self.editor.log.warning(
                    'Voice recognition not available - microphone not found',
                )
                self.editor.voice_manager = None

        except ImportError, OSError, AttributeError, RuntimeError:
            self.editor.log.exception('Failed to initialize voice recognition')
            self.editor.voice_manager = None

    # ------------------------------------------------------------------
    # Undo / redo system
    # ------------------------------------------------------------------

    def init_undo_redo_system(self) -> None:
        """Initialize the undo/redo system with all operation trackers.

        Each tracker receives the editor so that Command objects
        can reach the canvas, film strips, and other subsystems directly.
        """
        self.editor.undo_redo_manager = UndoRedoManager(max_history=50)
        self.editor.canvas_operation_tracker = CanvasOperationTracker(
            self.editor.undo_redo_manager,
            editor=self.editor,
        )
        self.editor.film_strip_operation_tracker = FilmStripOperationTracker(
            self.editor.undo_redo_manager,
            editor=self.editor,
        )
        self.editor.cross_area_operation_tracker = CrossAreaOperationTracker(
            self.editor.undo_redo_manager,
            editor=self.editor,
        )
        self.editor.controller_position_operation_tracker = ControllerPositionOperationTracker(
            self.editor.undo_redo_manager,
            editor=self.editor,
        )

        # The delegate initializes private editor attributes here because they are
        # logically part of the undo/redo system setup. The delegate is tightly coupled
        # to BitmapEditorScene by design.
        self.editor.current_pixel_changes = []
        self.editor._is_drag_operation = False  # pyright: ignore[reportPrivateUsage]
        self.editor._pixel_change_timer = None  # pyright: ignore[reportPrivateUsage]
        self.editor._applying_undo_redo = False  # pyright: ignore[reportPrivateUsage]

        # These are set up in the GameEngine class.
        if not hasattr(self.editor, '_initialized'):
            self.editor.log.info(f'Game Options: {self.editor.options}')

            # Override font to use a cleaner system font
            self.editor.options['font_name'] = 'arial'
            self.editor.log.info(f'Font overridden to: {self.editor.options["font_name"]}')
            self.editor._initialized = True  # pyright: ignore[reportPrivateUsage]
