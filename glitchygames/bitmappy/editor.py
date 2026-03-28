#!/usr/bin/env python3
"""Glitchy Games Bitmap Editor."""

from __future__ import annotations

import contextlib
import logging
import multiprocessing
import signal
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, override

import pygame

# Try to import voice recognition, but don't fail if it's not available
try:
    from glitchygames.events.voice import VoiceEventManager
except ImportError:
    VoiceEventManager = None  # ty: ignore[invalid-assignment]

from glitchygames import events
from glitchygames.color import (
    RGBA_COMPONENT_COUNT,
)
from glitchygames.engine import GameEngine
from glitchygames.pixels import rgb_triplet_generator
from glitchygames.scenes import Scene
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.ui import (
    ColorWellSprite,
    MenuBar,
    MenuItem,
    MultiLineTextBox,
    SliderSprite,
    TabControlSprite,
    TextSprite,
)
from glitchygames.ui.dialogs import (
    LoadDialogScene,
    NewCanvasDialogScene,
    SaveDialogScene,
)

from .ai_manager import AIManager
from .animated_canvas import AnimatedCanvasSprite
from .constants import (
    LOG,
    MAGENTA_TRANSPARENT,
    MIN_FILM_STRIPS_FOR_PANEL_POSITIONING,
    MIN_PIXEL_DISPLAY_SIZE,
    PIXEL_CHANGE_DEBOUNCE_SECONDS,
)
from .controllers.event_handler import ControllerEventHandler
from .controllers.manager import MultiControllerManager
from .file_io import FileIOManager
from .film_strip_coordinator import FilmStripCoordinator
from .history.commands import FramePasteCommand
from .history.operations import (
    CanvasOperationTracker,
    ControllerPositionOperationTracker,
    CrossAreaOperationTracker,
    FilmStripOperationTracker,
)
from .history.undo_redo import UndoRedoManager
from .indicators.collision import VisualCollisionManager
from .slider_manager import SliderManager
from .sprite_inspection import load_ai_training_data
from .utils import resource_path

if TYPE_CHECKING:
    import argparse
    import types

    from .controllers.selection import ControllerSelection
    from .film_strip import FilmStripWidget
    from .film_strip_sprite import FilmStripSprite
    from .scroll_arrow import ScrollArrowSprite


class BitmapEditorScene(Scene):  # noqa: PLR0904
    """Bitmap Editor Scene.

    The scene expects a 'size' option in the format "WIDTHxHEIGHT" (e.g., "800x600")
    when initialized. This corresponds to the -s command line parameter.
    """

    log = LOG

    # Slider/color well attributes (created by SliderManager.setup_sliders_and_color_well)
    red_slider: SliderSprite
    green_slider: SliderSprite
    blue_slider: SliderSprite
    alpha_slider: SliderSprite
    color_well: ColorWellSprite
    tab_control: TabControlSprite
    slider_input_format: str

    # Set your game name/version here.
    NAME = 'Bitmappy'
    VERSION = '1.0'

    def _setup_menu_bar(self) -> None:
        """Set up the menu bar and menu items."""
        menu_bar_height = 24  # Taller menu bar

        # Different heights for icon vs text items
        icon_height = 16  # Smaller height for icon
        menu_item_height = menu_bar_height  # Full height for text items

        # Different vertical offsets for icon vs text
        icon_y = (menu_bar_height - icon_height) // 2 - 2  # Center the icon and move up 2px
        menu_item_y = 0  # Text items use full height

        # Create the menu bar using the UI library's MenuBar
        self.menu_bar = MenuBar(
            name='Menu Bar',
            x=0,
            y=0,
            width=self.screen_width,
            height=menu_bar_height,
            groups=self.all_sprites,
        )

        # Add the raspberry icon with its specific height
        icon_path = resource_path('glitcygames', 'assets', 'raspberry.toml')
        self.menu_icon = MenuItem(
            name=None,
            x=4,  # Add 4px offset from left edge
            y=icon_y,
            width=16,
            height=icon_height,  # Use icon-specific height
            filename=str(icon_path),
            groups=self.all_sprites,
        )
        self.menu_bar.add_menu(self.menu_icon)

        # Add all menus with full height
        menu_item_x = 0  # Start at left edge
        icon_width = 16  # Width of the raspberry icon
        menu_spacing = 2  # Reduced spacing between items
        menu_item_width = 48
        border_offset = self.menu_bar.border_width  # Usually 2px

        # Start after icon, compensating for border
        menu_item_x = (icon_width + menu_spacing) - border_offset

        new_menu = MenuItem(
            name='New',
            x=menu_item_x,
            y=menu_item_y - border_offset,  # Compensate for y border too
            width=menu_item_width,
            height=menu_item_height,
            groups=self.all_sprites,
        )
        self.menu_bar.add_menu(new_menu)

        # Move to next position
        menu_item_x += menu_item_width + menu_spacing

        save_menu = MenuItem(
            name='Save',
            x=menu_item_x,
            y=menu_item_y - border_offset,
            width=menu_item_width,
            height=menu_item_height,
            groups=self.all_sprites,
        )
        self.menu_bar.add_menu(save_menu)

        # Move to next position
        menu_item_x += menu_item_width + menu_spacing

        load_menu = MenuItem(
            name='Load',
            x=menu_item_x,
            y=menu_item_y - border_offset,
            width=menu_item_width,
            height=menu_item_height,
            groups=self.all_sprites,
        )
        self.menu_bar.add_menu(load_menu)

    def _setup_canvas(self, options: dict[str, Any]) -> None:
        """Set up the canvas sprite."""
        # Calculate canvas dimensions and pixel size
        pixels_across, pixels_tall, pixel_size = self._calculate_canvas_dimensions(options)

        # Create animated sprite with single frame
        animated_sprite = self._create_animated_sprite(pixels_across, pixels_tall)

        # Store the animated sprite as the shared instance
        self.animated_sprite = animated_sprite

        # Create the main canvas sprite
        self._create_canvas_sprite(animated_sprite, pixels_across, pixels_tall, pixel_size)

        # Finalize setup and start animation
        self._finalize_canvas_setup(animated_sprite, options)

    def _calculate_canvas_dimensions(self, options: dict[str, Any]) -> tuple[int, int, int]:
        """Calculate canvas dimensions and pixel size.

        Args:
            options: Dictionary containing canvas configuration

        Returns:
            Tuple of (pixels_across, pixels_tall, pixel_size)

        """
        menu_bar_height = 24
        bottom_margin = 80  # Space needed for sliders and color well
        available_height = (
            self.screen_height - bottom_margin - menu_bar_height
        )  # Use menu_bar_height instead of 32

        # Calculate pixel size to fit the canvas in the available space
        width, height = options['size'].split('x')
        pixels_across = int(width)
        pixels_tall = int(height)

        # ===== DEBUG: INITIAL CANVAS SIZING =====
        LOG.debug('===== DEBUG: INITIAL CANVAS SIZING =====')
        LOG.debug(
            f'Screen: {self.screen_width}x{self.screen_height}, Sprite:'
            f' {pixels_across}x{pixels_tall}',
        )
        LOG.debug(f'Available height: {available_height}')
        LOG.debug(f'Height constraint: {available_height // pixels_tall}')
        LOG.debug(f'Width constraint: {(self.screen_width * 1 // 2) // pixels_across}')
        LOG.debug(f'350px width constraint: {350 // pixels_across}')
        LOG.debug(f'320x320 constraint: {320 // max(pixels_across, pixels_tall)}')

        # Calculate pixel size based on available space
        pixel_size = min(
            available_height // pixels_tall,  # Height-based size
            # Width-based size (use 1/2 of screen width)
            (self.screen_width * 1 // 2) // pixels_across,
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
        self.canvas = AnimatedCanvasSprite(
            animated_sprite=animated_sprite,
            name='Animated Bitmap Canvas',
            x=0,
            y=menu_bar_height,  # Position canvas right below menu bar
            pixels_across=pixels_across,
            pixels_tall=pixels_tall,
            pixel_width=pixel_size,
            pixel_height=pixel_size,
            groups=self.all_sprites,
        )

        # Set parent scene reference for canvas
        self.canvas.parent_scene = self

        # Debug: Log canvas position and size
        self.log.info(
            'AnimatedCanvasSprite created at position '
            f'({self.canvas.rect.x}, {self.canvas.rect.y}) with size {self.canvas.rect.size}',
        )
        self.log.info(f'AnimatedCanvasSprite groups: {self.canvas.groups}')
        self.log.info(f'AnimatedCanvasSprite dirty: {self.canvas.dirty}')

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

    def _setup_debug_text_box(self) -> None:
        """Set up the debug text box and AI label."""
        # Calculate debug text box position and size - align to bottom right corner
        debug_height = 186  # Fixed height for AI chat box

        # Calculate film strip left x position (should be less than color well's right x - 1)
        if hasattr(self, 'color_well') and self.color_well:
            film_strip_left_x = (
                self.color_well.rect.right + 1
            )  # Film strip left x = color well right x + 1
        else:
            # Fallback if color well not available
            film_strip_left_x = self.screen_width - 200

        # AI sprite box should be clamped to right side of screen and grow left
        # but not grow left more than the film strip left x
        debug_x = film_strip_left_x  # Start from film strip left x
        debug_width = self.screen_width - debug_x  # Extend to right edge of screen

        # Position below the 2nd film strip if it exists, otherwise clamp to bottom of screen
        if (
            hasattr(self, 'film_strips')
            and self.film_strips
            and len(self.film_strips) >= MIN_FILM_STRIPS_FOR_PANEL_POSITIONING
        ):
            # Find the bottom of the 2nd film strip
            second_strip_bottom = 0
            # Safely get the second film strip to handle race conditions during sprite loading
            try:
                # Convert to list to safely access by index
                film_strip_list = list(self.film_strips.values())
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
            debug_y = min(debug_y, self.screen_height - debug_height)
        else:
            # Fallback: clamp to bottom of screen
            debug_y = self.screen_height - debug_height

        # Create the AI label
        label_height = 20
        self.ai_label = TextSprite(
            x=int(debug_x),
            y=debug_y - label_height,  # Position above the text box
            width=int(debug_width),
            height=label_height,
            text='AI Sprite',
            text_color=(255, 255, 255),  # White text
            background_color=(0, 0, 0),  # Solid black background like color well
            groups=self.all_sprites,
        )

        # Create the debug text box
        self.debug_text = MultiLineTextBox(
            name='Debug Output',
            x=int(debug_x),
            y=debug_y,
            width=int(debug_width),
            height=debug_height,
            text='',  # Changed to empty string
            parent=self,  # Pass self as parent
            groups=self.all_sprites,
        )

    def _update_ai_sprite_position(self) -> None:
        """Update AI sprite positioning when canvas changes."""
        if not hasattr(self, 'ai_label') or not hasattr(self, 'debug_text'):
            return  # AI sprites not initialized yet

        # Calculate new position using same logic as _setup_debug_text_box
        debug_height = 186  # Fixed height for AI chat box

        # Calculate film strip left x position (should be less than color well's right x - 1)
        if hasattr(self, 'color_well') and self.color_well:
            film_strip_left_x = (
                self.color_well.rect.right + 1
            )  # Film strip left x = color well right x + 1
        else:
            # Fallback if color well not available
            film_strip_left_x = self.screen_width - 200

        # AI sprite box should be clamped to right side of screen and grow left
        # but not grow left more than the film strip left x
        debug_x = film_strip_left_x  # Start from film strip left x
        debug_width = self.screen_width - debug_x  # Extend to right edge of screen

        # Position below the 2nd film strip if it exists, otherwise clamp to bottom of screen
        if (
            hasattr(self, 'film_strips')
            and self.film_strips
            and len(self.film_strips) >= MIN_FILM_STRIPS_FOR_PANEL_POSITIONING
        ):
            # Find the bottom of the 2nd film strip
            second_strip_bottom = 0
            # Safely get the second film strip to handle race conditions during sprite loading
            try:
                # Convert to list to safely access by index
                film_strip_list = list(self.film_strips.values())
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
            debug_y = min(debug_y, self.screen_height - debug_height)
        else:
            # Fallback: clamp to bottom of screen
            debug_y = self.screen_height - debug_height

        # Update AI label position
        self.ai_label.rect.x = debug_x
        self.ai_label.rect.y = debug_y - 20  # Position above the text box
        self.ai_label.rect.width = debug_width
        self.ai_label.rect.height = 20

        # Update debug text position
        self.debug_text.rect.x = debug_x
        self.debug_text.rect.y = debug_y
        self.debug_text.rect.width = debug_width
        self.debug_text.rect.height = debug_height

    def _setup_voice_recognition(self) -> None:
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

        All commands trigger the _clear_ai_sprite_box() callback.

        **To Enable:**
        1. Uncomment the call to self._setup_voice_recognition() in setup() (line ~6414)
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
                self.log.info('Voice recognition not available')
                self.voice_manager = None
                return
            self.voice_manager = VoiceEventManager(logger=self.log)

            if self.voice_manager.is_available():
                # Register voice commands
                self.voice_manager.register_command(
                    'clear the ai sprite box',
                    self._clear_ai_sprite_box,
                )
                self.voice_manager.register_command(
                    'clear ai sprite box',
                    self._clear_ai_sprite_box,
                )
                self.voice_manager.register_command('clear ai box', self._clear_ai_sprite_box)
                # Add commands for what speech recognition actually hears
                self.voice_manager.register_command(
                    'clear the ai sprite',
                    self._clear_ai_sprite_box,
                )
                self.voice_manager.register_command('clear ai sprite', self._clear_ai_sprite_box)
                # Add command for "window" variation
                self.voice_manager.register_command(
                    'clear the ai sprite window',
                    self._clear_ai_sprite_box,
                )
                self.voice_manager.register_command(
                    'clear ai sprite window',
                    self._clear_ai_sprite_box,
                )

                # Start listening for voice commands
                self.voice_manager.start_listening()
                self.log.info('Voice recognition initialized and started')
            else:
                self.log.warning('Voice recognition not available - microphone not found')
                self.voice_manager = None

        except ImportError, OSError, AttributeError, RuntimeError:
            self.log.exception('Failed to initialize voice recognition')
            self.voice_manager = None

    def _clear_ai_sprite_box(self) -> None:
        """Clear the AI sprite text box."""
        if hasattr(self, 'debug_text') and self.debug_text:
            self.debug_text.text = ''
            self.log.info('AI sprite box cleared via voice command')
        else:
            self.log.warning('Cannot clear AI sprite box - debug_text not available')

    def __init__(
        self,
        options: dict[str, Any],
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize the Bitmap Editor Scene.

        Args:
            options: Dictionary of configuration options for the scene.
            groups: Optional pygame sprite groups for sprite management.

        Raises:
            None

        """
        if options is None:  # type: ignore[reportUnnecessaryComparison]
            options = {}

        # Set default size if not provided
        if 'size' not in options:
            options['size'] = '32x32'  # Default canvas size

        super().__init__(options=options, groups=groups)  # type: ignore[arg-type]

        # Initialize film strip scrolling attributes
        self.film_strip_scroll_offset = 0
        self.max_visible_strips = 2

        # Legacy film_strip_widget reference for backward compatibility
        # Used by _refresh_all_film_strip_widgets and undo/redo methods
        self.film_strip_widget: FilmStripWidget | None = None

        # Pixel change tracking dict for deduplication (used alongside _current_pixel_changes list)
        self.current_pixel_changes_dict: dict[
            int,
            tuple[int, tuple[int, ...], tuple[int, ...]],
        ] = {}

        # Initialize scroll arrows
        self.scroll_up_arrow = None

        # Initialize mouse drag scrolling state
        self.film_strip_drag_start_y = None
        self.film_strip_drag_start_offset = None
        self.is_dragging_film_strips = False

        # Initialize film strip state (populated by FilmStripCoordinator.setup_film_strips)
        self.film_strips: dict[str, FilmStripWidget] = {}
        self.film_strip_sprites: dict[str, FilmStripSprite] = {}
        self.scroll_up_arrow: ScrollArrowSprite | None = None

        # Initialize selection state for multi-selection system
        self.selected_animation: str | None = ''
        self.selected_frame: int | None = 0

        # OLD SYSTEM REMOVED - Using new multi-controller system instead

        # Debug state tracking to prevent redundant logging
        self._last_debug_controller_animation = ''
        self._last_debug_controller_frame = -1
        self._last_debug_keyboard_animation = ''
        self._last_debug_keyboard_frame = -1

        # Initialize multi-controller system
        self.multi_controller_manager = MultiControllerManager()
        self.controller_selections: dict[int, ControllerSelection] = {}

        # Initialize mode switching system
        from glitchygames.bitmappy.controllers.modes import ModeSwitcher

        # Initialize undo/redo system
        self._init_undo_redo_system()

        self.mode_switcher = ModeSwitcher()
        self.visual_collision_manager = VisualCollisionManager()

        # Selected frame visibility toggle for canvas comparison
        self.selected_frame_visible = True

        # Initialize extracted subsystem managers
        self._file_io = FileIOManager(self)
        self._ai_integration = AIManager(self)
        self._slider_manager = SliderManager(self)
        self.controller_handler = ControllerEventHandler(self)
        self.mode_switcher.set_handler(self.controller_handler)
        self.film_strip_coordinator = FilmStripCoordinator(self)

        # Set up all components
        self._setup_menu_bar()
        self._setup_canvas(options)
        self._slider_manager.setup_sliders_and_color_well()
        self._setup_debug_text_box()

        # Set up film strips after canvas is ready
        self.film_strip_coordinator.setup_film_strips()

        # Set up callback for when sprites are loaded
        if hasattr(self, 'canvas') and self.canvas:
            # Set up the callback on the canvas to call the main scene
            self.canvas.on_sprite_loaded = self.film_strip_coordinator.on_sprite_loaded  # type: ignore[attr-defined] # ty: ignore[invalid-assignment]
            self.log.debug('Set up on_sprite_loaded callback for canvas')
            LOG.debug('DEBUG: Set up on_sprite_loaded callback for canvas')

        # Controller selection will be initialized when START button is pressed

        # Voice recognition is currently disabled.
        # See _setup_voice_recognition() for details about enabling it.

        self.all_sprites.clear(self.screen, self.background)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    def _init_undo_redo_system(self) -> None:
        """Initialize the undo/redo system with all operation trackers.

        Each tracker receives ``self`` (the editor) so that Command objects
        can reach the canvas, film strips, and other subsystems directly.
        """
        self.undo_redo_manager = UndoRedoManager(max_history=50)
        self.canvas_operation_tracker = CanvasOperationTracker(self.undo_redo_manager, editor=self)
        self.film_strip_operation_tracker = FilmStripOperationTracker(
            self.undo_redo_manager,
            editor=self,
        )
        self.cross_area_operation_tracker = CrossAreaOperationTracker(
            self.undo_redo_manager,
            editor=self,
        )
        self.controller_position_operation_tracker = ControllerPositionOperationTracker(
            self.undo_redo_manager,
            editor=self,
        )

        self.current_pixel_changes: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
        self._is_drag_operation: bool = False
        self._pixel_change_timer: float | None = None
        self._applying_undo_redo: bool = False
        self._frame_clipboard: dict[str, Any] | None = None

        # These are set up in the GameEngine class.
        if not hasattr(self, '_initialized'):
            self.log.info(f'Game Options: {self.options}')

            # Override font to use a cleaner system font
            self.options['font_name'] = 'arial'
            self.log.info(f'Font overridden to: {self.options["font_name"]}')
            self._initialized = True

    @override
    def on_menu_item_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the menu item event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        self.log.info('Scene got menu item event: %s', event)
        if not event.menu.name:
            # This is for the system menu.
            self.log.info('System Menu Clicked')
        elif event.menu.name == 'New':
            self.on_new_canvas_dialog_event(event=event)
        elif event.menu.name == 'Save':
            self.on_save_dialog_event(event=event)
        elif event.menu.name == 'Load':
            self.on_load_dialog_event(event=event)
        elif event.menu.name == 'Quit':
            self.log.info('User quit from menu item.')
            self.scene_manager.quit()
        else:
            self.log.info(f'Unhandled Menu Item: {event.menu.name}')
        self.dirty = 1

    # NB: Keepings this around causes GG-7 not to manifest... curious.
    # This function is extraneous now that on_new_canvas_dialog_event exists.
    #
    # There is also some dialog drawing goofiness when keeping this which
    # goes away when we remove it.
    #
    # Keeping as a workaround for GG-7 for now.
    def _reset_canvas_for_new_file(self, width: int, height: int, pixel_size: int) -> None:
        """Reset canvas state for a new file with the given dimensions.

        Args:
            width: Canvas width in pixels.
            height: Canvas height in pixels.
            pixel_size: Display pixel size.

        """
        self.canvas.pixels_across = width
        self.canvas.pixels_tall = height
        self.canvas.pixel_width = pixel_size
        self.canvas.pixel_height = pixel_size

        self.canvas.pixels = [(255, 0, 255, 255)] * (width * height)  # ty: ignore[invalid-assignment]
        self.canvas.dirty_pixels = [True] * len(self.canvas.pixels)

        # Reset viewport/panning system
        if hasattr(self.canvas, 'reset_panning'):
            self.canvas.reset_panning()
        if hasattr(self.canvas, '_panning_active'):
            self.canvas._panning_active = False  # type: ignore[reportPrivateUsage]
        if hasattr(self.canvas, 'pan_offset_x'):
            self.canvas.pan_offset_x = 0
        if hasattr(self.canvas, 'pan_offset_y'):
            self.canvas.pan_offset_y = 0

    def _create_fresh_animated_sprite(self, width: int, height: int, pixel_size: int) -> None:
        """Create a fresh animated sprite and update the canvas.

        Args:
            width: Sprite width in pixels.
            height: Sprite height in pixels.
            pixel_size: Display pixel size.

        """
        from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

        fresh_sprite = AnimatedSprite()
        fresh_sprite.name = 'new_canvas'
        fresh_sprite.description = 'New canvas sprite'

        fresh_frame = SpriteFrame(surface=pygame.Surface((width, height)))
        fresh_frame.set_pixel_data([(255, 0, 255)] * (width * height))  # ty: ignore[invalid-argument-type]

        fresh_sprite._animations['default'] = [fresh_frame]  # type: ignore[reportPrivateUsage]
        fresh_sprite.frame_manager.current_animation = 'default'
        fresh_sprite.frame_manager.current_frame = 0

        self.canvas.animated_sprite = fresh_sprite
        self.canvas.image = pygame.Surface((width * pixel_size, height * pixel_size))
        self.canvas.rect = self.canvas.image.get_rect(x=0, y=24)
        self.canvas._update_border_thickness()  # type: ignore[reportPrivateUsage]
        self.canvas.force_redraw()

    def on_new_file_event(self: Self, dimensions: str) -> None:
        """Handle the new file event.

        Args:
            dimensions (str): The canvas dimensions in WxH format.

        """
        self.log.info('Creating new canvas with dimensions: %s', dimensions)

        try:
            width, height = map(int, dimensions.lower().split('x'))
            self.log.info('Parsed dimensions: %sx%s', width, height)

            available_height = self.screen_height - 80 - 24
            new_pixel_size = min(
                available_height // height,
                (self.screen_width * 1 // 2) // width,
                350 // width,
            )
            self.log.info('Calculated new pixel size: %s', new_pixel_size)

            self._reset_canvas_for_new_file(width, height, new_pixel_size)
            self._create_fresh_animated_sprite(width, height, new_pixel_size)
            self.film_strip_coordinator.clear_film_strips_for_new_canvas()
            self._clear_ai_sprite_box()

            if hasattr(self, '_ai_integration'):
                self._ai_integration.pending_ai_requests.clear()
                self.log.info('Cleared AI request cache for new canvas')

            self._update_ai_sprite_position()
            self.canvas.update()
            self.canvas.dirty = 1
            self.log.info(
                'Canvas resized to %sx%s with pixel size %s',
                width,
                height,
                new_pixel_size,
            )

        except ValueError:
            self.log.exception("Invalid dimensions format '%s'", dimensions)
            self.log.exception("Expected format: WxH (e.g., '32x32')")

        self.dirty = 1

    def on_new_canvas_dialog_event(self: Self, event: events.HashableEvent) -> None:  # noqa: ARG002
        """Handle the new canvas dialog event."""
        # Create a fresh dialog scene each time
        new_canvas_dialog_scene = NewCanvasDialogScene(options=self.options, previous_scene=self)
        # Set the dialog's background to the screenshot
        new_canvas_dialog_scene.background = self.screenshot
        self.next_scene = new_canvas_dialog_scene
        self.dirty = 1

    def on_load_dialog_event(self: Self, event: events.HashableEvent) -> None:  # noqa: ARG002
        """Handle the load dialog event."""
        # Create a fresh dialog scene each time
        load_dialog_scene = LoadDialogScene(options=self.options, previous_scene=self)
        # Set the dialog's background to the screenshot
        load_dialog_scene.background = self.screenshot
        self.next_scene = load_dialog_scene
        self.dirty = 1

    def on_save_dialog_event(self: Self, event: events.HashableEvent) -> None:  # noqa: ARG002
        """Handle the save dialog event."""
        # Create a fresh dialog scene each time
        save_dialog_scene = SaveDialogScene(options=self.options, previous_scene=self)
        # Set the dialog's background to the screenshot
        save_dialog_scene.background = self.screenshot
        self.next_scene = save_dialog_scene
        self.dirty = 1

    def on_color_well_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle the color well event by delegating to SliderManager."""
        self._slider_manager.on_color_well_event(event, trigger)

    def on_slider_event(
        self: Self,
        event: events.HashableEvent,
        trigger: events.HashableEvent,
    ) -> None:
        """Handle the slider event by delegating to SliderManager."""
        self._slider_manager.on_slider_event(event, trigger)

    @override
    def on_right_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the right mouse button up event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        # Check for shift-right-click (screen sampling)
        is_shift_click = (
            pygame.key.get_pressed()[pygame.K_LSHIFT] or pygame.key.get_pressed()[pygame.K_RSHIFT]
        )

        # First, check if any sprites have handled the event
        collided_sprites = self.sprites_at_position(pos=event.pos)
        for sprite in collided_sprites:
            if hasattr(sprite, 'on_right_mouse_button_up_event'):
                result = sprite.on_right_mouse_button_up_event(event)
                if result:  # Event was handled by sprite
                    return

        # If no sprite handled the event, proceed with scene-level handling
        # Check if the click is on the canvas to sample canvas pixel data
        if self._sample_canvas_pixel(event, is_shift_click=is_shift_click):
            return

        # Fallback to screen sampling (RGB only)
        try:
            assert self.screen is not None
            color = tuple(self.screen.get_at(event.pos))
            if len(color) == RGBA_COMPONENT_COUNT:
                red, green, blue, _ = color  # Ignore alpha from screen
            else:
                red, green, blue = color
            alpha = 255  # Screen has no alpha, default to opaque
            self.log.info(
                'Screen pixel sampled - Red: %s, Green: %s, Blue: %s, Alpha: %s (default)',
                red,
                green,
                blue,
                alpha,
            )

            # Update sliders with RGB values and default alpha
            trigger = events.HashableEvent(0, name='R', value=red)
            self.on_slider_event(event=event, trigger=trigger)

            trigger = events.HashableEvent(0, name='G', value=green)
            self.on_slider_event(event=event, trigger=trigger)

            trigger = events.HashableEvent(0, name='B', value=blue)
            self.on_slider_event(event=event, trigger=trigger)

            trigger = events.HashableEvent(0, name='A', value=alpha)
            self.on_slider_event(event=event, trigger=trigger)
        except IndexError:
            pass

    def _sample_canvas_pixel(
        self,
        event: events.HashableEvent,
        *,
        is_shift_click: bool,
    ) -> bool:
        """Sample a pixel from the canvas and update sliders.

        Args:
            event: The mouse event with position.
            is_shift_click: Whether shift was held during the click.

        Returns:
            True if a canvas pixel was sampled, False otherwise.

        """
        if not (
            hasattr(self, 'canvas')
            and self.canvas
            and self.canvas.rect is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.canvas.rect.collidepoint(event.pos)
        ):
            return False

        if is_shift_click:
            # Shift-right-click: sample screen directly (RGB only)
            self.log.info('Shift-right-click detected on canvas - sampling screen directly')
            self._slider_manager.sample_color_from_screen(event.pos)
            return True

        # Regular right-click: sample from canvas pixel data (RGBA)
        canvas_x = (event.pos[0] - self.canvas.rect.x) // self.canvas.pixel_width
        canvas_y = (event.pos[1] - self.canvas.rect.y) // self.canvas.pixel_height

        if not (
            0 <= canvas_x < self.canvas.pixels_across and 0 <= canvas_y < self.canvas.pixels_tall
        ):
            return False

        pixel_num = canvas_y * self.canvas.pixels_across + canvas_x
        if pixel_num >= len(self.canvas.pixels):
            return False

        color: tuple[int, ...] = self.canvas.pixels[pixel_num]  # type: ignore[assignment]

        # Handle both RGB and RGBA pixel formats
        if len(color) == RGBA_COMPONENT_COUNT:  # type: ignore[reportUnknownArgumentType]
            red, green, blue, alpha = (
                int(color[0]),  # pyright: ignore[reportUnknownArgumentType]
                int(color[1]),  # pyright: ignore[reportUnknownArgumentType]
                int(color[2]),  # pyright: ignore[reportUnknownArgumentType]
                int(color[3]),  # pyright: ignore[reportUnknownArgumentType]
            )
        else:
            red, green, blue = int(color[0]), int(color[1]), int(color[2])  # type: ignore[reportUnknownArgumentType]
            alpha = 255  # Default to opaque for RGB pixels

        self.log.info(
            'Canvas pixel sampled - Red: %s, Green: %s, Blue: %s, Alpha: %s',
            red,
            green,
            blue,
            alpha,
        )

        # Update all sliders with the sampled RGBA values
        for name, value in [('R', red), ('G', green), ('B', blue), ('A', alpha)]:
            trigger = events.HashableEvent(0, name=name, value=value)
            self.on_slider_event(event=event, trigger=trigger)
        return True

    @override
    def on_left_mouse_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the left mouse button down event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        sprites = self.sprites_at_position(pos=event.pos)

        # Check for clicks on scroll arrows first (only if visible)
        if self._handle_scroll_arrow_click(sprites):
            return

        # Check if click is on any slider text box and deactivate others
        clicked_slider = self._slider_manager.detect_clicked_slider(event.pos)

        # Deactivate all slider text boxes except the one clicked (if any)
        # Also commit values when clicking outside of any slider text box
        for slider_name in ('red', 'green', 'blue'):
            slider_attr = f'{slider_name}_slider'
            if hasattr(self, slider_attr):
                self._slider_manager.commit_and_deactivate_slider(
                    getattr(self, slider_attr),
                    clicked_slider,
                    slider_name,
                )

        # If a slider text box was clicked, also trigger the slider's normal behavior
        if clicked_slider is not None:
            slider_attr = f'{clicked_slider}_slider'
            if hasattr(self, slider_attr):
                getattr(self, slider_attr).on_left_mouse_button_down_event(event)

        # Handle other sprite clicks
        for sprite in sprites:
            sprite.on_left_mouse_button_down_event(event)

        # Check if click is in film strip area for drag scrolling (only if no sprite handled it)
        if self.film_strip_coordinator.is_mouse_in_film_strip_area(event.pos):
            self.is_dragging_film_strips = True
            self.film_strip_drag_start_y = event.pos[1]
            self.film_strip_drag_start_offset = self.film_strip_scroll_offset
            self.log.debug(
                f'Started film strip drag at Y={event.pos[1]},'
                f' offset={self.film_strip_scroll_offset}',
            )

    def _handle_scroll_arrow_click(self, sprites: list[Any]) -> bool:
        """Handle clicks on scroll arrow sprites.

        Args:
            sprites: List of sprites at the click position.

        Returns:
            True if a scroll arrow was clicked and handled.

        """
        for sprite in sprites:
            if hasattr(sprite, 'direction') and hasattr(sprite, 'visible') and sprite.visible:
                LOG.debug(
                    f'Scroll arrow clicked: direction={sprite.direction}, visible={sprite.visible}',
                )
                if sprite.direction == 'up':
                    LOG.debug('Navigating to previous animation')
                    if hasattr(self, 'canvas') and self.canvas:
                        self.canvas.previous_animation()
                        self.film_strip_coordinator.scroll_to_current_animation()
                        self.film_strip_coordinator.update_film_strips_for_animated_sprite_update()
                    return True
        return False

    def on_tab_change_event(self, tab_format: str) -> None:
        """Handle tab control format change by delegating to SliderManager."""
        self._slider_manager.on_tab_change_event(tab_format)

    @override
    def on_left_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the left mouse button up event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        # Stop film strip drag scrolling if active
        if self.is_dragging_film_strips:
            self.is_dragging_film_strips = False
            self.film_strip_drag_start_y = None
            self.film_strip_drag_start_offset = None
            self.log.debug('Stopped film strip drag scrolling')

        sprites = self.sprites_at_position(pos=event.pos)

        for sprite in sprites:
            sprite.on_left_mouse_button_up_event(event)

    @override
    def on_left_mouse_drag_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle the left mouse drag event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Raises:
            None

        """
        # Handle film strip drag scrolling
        if self.is_dragging_film_strips:
            self.log.debug(f'Handling film strip drag at Y={event.pos[1]}')
            self.film_strip_coordinator.handle_film_strip_drag_scroll(event.pos[1])
            return  # Don't process other drag events when dragging film strips

        # Optimized: If dragging on canvas, skip expensive sprite collision detection
        # The canvas already handles its own drag events efficiently
        if (
            hasattr(self, 'canvas')
            and self.canvas is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.canvas.rect is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.canvas.rect.collidepoint(event.pos)
        ):
            # Directly call canvas drag handler - skip sprite iteration
            self.canvas.on_left_mouse_drag_event(event, trigger)
            return

        # Only do expensive sprite iteration if not dragging on canvas
        self.canvas.on_left_mouse_drag_event(event, trigger)

        try:
            sprites = self.sprites_at_position(pos=event.pos)

            for sprite in sprites:
                sprite.on_left_mouse_drag_event(event, trigger)
        except AttributeError:
            pass

    @override
    def on_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle mouse button up events."""
        # Check if debug text box should handle the event
        if (
            hasattr(self, 'debug_text')
            and self.debug_text is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.debug_text.rect is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.debug_text.rect.collidepoint(event.pos)
        ):
            self.debug_text.on_mouse_up_event(event)
            return

        # Submit collected pixel changes for undo/redo tracking
        self._submit_pixel_changes_if_ready()

        # Reset drag operation flag
        self._is_drag_operation = False

        # Always release all sliders on mouse up to prevent stickiness
        if (
            hasattr(self, 'red_slider')
            and hasattr(self.red_slider, 'dragging')
            and self.red_slider.dragging
        ):
            self.red_slider.dragging = False
            self.red_slider.on_left_mouse_button_up_event(event)
        if (
            hasattr(self, 'green_slider')
            and hasattr(self.green_slider, 'dragging')
            and self.green_slider.dragging
        ):
            self.green_slider.dragging = False
            self.green_slider.on_left_mouse_button_up_event(event)
        if (
            hasattr(self, 'blue_slider')
            and hasattr(self.blue_slider, 'dragging')
            and self.blue_slider.dragging
        ):
            self.blue_slider.dragging = False
            self.blue_slider.on_left_mouse_button_up_event(event)

        # Pass to other sprites
        for sprite in self.all_sprites:
            if hasattr(sprite, 'on_mouse_button_up_event') and sprite.rect.collidepoint(event.pos):
                sprite.on_mouse_button_up_event(event)

    @override
    def on_mouse_drag_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle
            trigger (object): The trigger object

        """
        for sprite in self.all_sprites:
            if hasattr(sprite, 'on_mouse_drag_event'):
                sprite.on_mouse_drag_event(event, trigger)

    @override
    def on_mouse_motion_event(self: Self, event: events.HashableEvent) -> None:
        """Handle mouse motion events.

        Args:
            event (pygame.event.Event): The event to handle

        """
        # Handle slider hover effects
        self._slider_manager.update_slider_hover_effects(event.pos)

        for sprite in self.all_sprites:
            if hasattr(sprite, 'on_mouse_motion_event'):
                sprite.on_mouse_motion_event(event)

    # ──────────────────────────────────────────────────────────────────────
    # AI integration delegation (methods extracted to ai_integration.py)
    # ──────────────────────────────────────────────────────────────────────

    @override
    def on_text_submit_event(self, text: str) -> None:
        """Handle text submission by delegating to AIManager."""
        self._ai_integration.on_text_submit_event(text)

    @override
    def setup(self) -> None:
        """Set up the bitmap editor scene."""
        super().setup()
        self._ai_integration.setup()

    def _update_animated_canvas(self) -> None:
        """Update the animated canvas with delta time, film strips, and frame transitions."""
        # Debug animation state
        if hasattr(self, '_debug_animation_counter'):
            self._debug_animation_counter += 1
        else:
            self._debug_animation_counter = 1

        # Log animation state approximately once per second, regardless of fps
        if not hasattr(self, '_last_animation_log_time'):
            self._last_animation_log_time = time.time()
        current_time = time.time()
        if current_time - self._last_animation_log_time >= 1.0:
            self._last_animation_log_time = current_time

        # Pass delta time to the canvas for animation updates
        self.canvas.update_animation(self.dt)

        self.film_strip_coordinator.update_film_strip_animation_timing()

        # Mark the main scene as dirty every frame to ensure sprite groups are updated
        self.dirty = 1

        # Render visual indicators for multi-controller system
        self.controller_handler.render_visual_indicators()

        # Check for frame transitions
        frame_index = self.canvas.animated_sprite.current_frame

        if not hasattr(self, '_last_animation_frame') or self._last_animation_frame != frame_index:
            self._last_animation_frame = frame_index

            # Don't update the canvas frame - it should stay on the frame being edited
            # Only the live preview should animate

            # Note: Live preview functionality is now integrated into the film strip

    @override
    def update(self) -> None:
        """Update scene state."""
        super().update()  # Call the base Scene.update() method

        # Update continuous slider adjustments
        self.controller_handler.update_continuous_adjustments()

        # Update continuous canvas movements
        self.controller_handler.update_continuous_movements()

        # Check for single click timer
        self._check_single_click_timer()

        # Update the animated canvas with delta time
        if (
            hasattr(self, 'canvas')
            and hasattr(self.canvas, 'animated_sprite')
            and self.canvas.animated_sprite
        ):
            self._update_animated_canvas()

        # Check for AI responses
        self._ai_integration.check_responses()

    def _cleanup_voice_recognition(self) -> None:
        """Clean up voice recognition resources.

        **STATUS: Part of disabled voice recognition feature**

        This method is called during scene teardown to properly release microphone
        resources and stop any background threads used by voice recognition.

        **Important:** Always call this even if voice recognition was never enabled,
        as it safely handles the case where voice_manager is None.

        This method:
        - Stops the voice recognition listening thread (if active)
        - Releases microphone resources
        - Clears the voice_manager reference
        - Logs success or error status

        See _setup_voice_recognition() documentation for more information about
        the voice recognition feature status.
        """
        if hasattr(self, 'voice_manager') and self.voice_manager:
            try:
                self.log.info('Stopping voice recognition...')
                self.voice_manager.stop_listening()
                self.voice_manager = None
                self.log.info('Voice recognition stopped successfully')
            except OSError, AttributeError, RuntimeError:
                self.log.exception('Error stopping voice recognition')

    @override
    def cleanup(self) -> None:
        """Clean up resources."""
        self.log.info('Starting cleanup...')

        self._ai_integration.cleanup()

        # Clean up voice recognition
        self._cleanup_voice_recognition()

        super().cleanup()

    @override
    def on_key_up_event(self, event: events.HashableEvent) -> None:
        """Handle key release events."""
        # Get modifier keys
        mod = event.mod if hasattr(event, 'mod') else 0

        # Check if this is a Ctrl+Shift+Arrow key release
        if (
            (mod & pygame.KMOD_CTRL)
            and (mod & pygame.KMOD_SHIFT)
            and hasattr(self, 'canvas')
            and self.canvas
            and event.key in {pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN}
        ):
            self.log.debug('Ctrl+Shift+Arrow key released - committing panned buffer')
            self._commit_panned_buffer()
            return

        # Call parent class handler
        super().on_key_up_event(event)

    def _build_surface_from_canvas_pixels(self) -> pygame.Surface:
        """Build a pygame Surface from the current canvas pixel data.

        Returns:
            A new SRCALPHA surface with the canvas pixels rendered onto it.

        """
        surface = pygame.Surface(
            (self.canvas.pixels_across, self.canvas.pixels_tall),
            pygame.SRCALPHA,
        )
        for y in range(self.canvas.pixels_tall):
            for x in range(self.canvas.pixels_across):
                pixel_num = y * self.canvas.pixels_across + x
                if pixel_num < len(self.canvas.pixels):
                    color = self.canvas.pixels[pixel_num]
                    surface.set_at((x, y), color)
        return surface

    def _commit_panned_frame_pixels(self, current_animation: str, current_frame: int) -> None:
        """Commit panned pixel data to the animation frame and its surface.

        Args:
            current_animation: Name of the current animation.
            current_frame: Index of the current frame.

        """
        frame = self.canvas.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
        if not hasattr(frame, 'pixels'):
            return

        # The current self.canvas.pixels already has the panned view
        frame.pixels = list(self.canvas.pixels)

        # Also update the frame.image surface for film strip thumbnails with alpha support
        frame.image = self._build_surface_from_canvas_pixels()
        self.log.debug(
            'Committed panned pixels and image to frame %s[%s]',
            current_animation,
            current_frame,
        )

    def _commit_panned_film_strip_frame(self, current_animation: str, current_frame: int) -> None:
        """Commit panned pixel data to the film strip's animation frame.

        Args:
            current_animation: Name of the current animation.
            current_frame: Index of the current frame.

        """
        if not (
            hasattr(self, 'film_strips')
            and self.film_strips
            and current_animation in self.film_strips
        ):
            return

        film_strip = self.film_strips[current_animation]
        if not (
            hasattr(film_strip, 'animated_sprite')
            and film_strip.animated_sprite
            and current_animation in film_strip.animated_sprite._animations  # type: ignore[reportPrivateUsage]
            and current_frame < len(film_strip.animated_sprite._animations[current_animation])  # type: ignore[reportPrivateUsage]
        ):
            return

        # Update the film strip's animated sprite frame data
        film_strip_frame = film_strip.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
        if not hasattr(film_strip_frame, 'pixels'):
            return

        film_strip_frame.pixels = list(self.canvas.pixels)

        # Also update the film strip frame's image surface with alpha support
        film_strip_frame.image = self._build_surface_from_canvas_pixels()
        self.log.debug(
            'Updated film strip animated sprite frame %s[%s] with pixels and image',
            current_animation,
            current_frame,
        )

    def _commit_panned_buffer(self) -> None:
        """Commit the panned buffer back to the real frame data."""
        if not hasattr(self, 'canvas') or not self.canvas:
            return

        # Get current frame key
        frame_key = self.canvas._get_current_frame_key()  # type: ignore[reportPrivateUsage]

        # Check if this frame has active panning
        if frame_key not in self.canvas._frame_panning:  # type: ignore[reportPrivateUsage]
            self.log.debug('No panning state for current frame')
            return

        frame_state = self.canvas._frame_panning[frame_key]  # type: ignore[reportPrivateUsage]
        if not frame_state['active']:
            self.log.debug('No active panning to commit')
            return

        # Commit the current panned pixels back to the frame
        if not (hasattr(self.canvas, 'animated_sprite') and self.canvas.animated_sprite):
            self.log.debug('Panned buffer committed, panning state preserved for continued panning')
            return

        current_animation = self.canvas.current_animation
        current_frame = self.canvas.current_frame

        if not (
            current_animation in self.canvas.animated_sprite._animations  # type: ignore[reportPrivateUsage]
            and current_frame < len(self.canvas.animated_sprite._animations[current_animation])  # type: ignore[reportPrivateUsage]
        ):
            self.log.debug('Panned buffer committed, panning state preserved for continued panning')
            return

        self._commit_panned_frame_pixels(current_animation, current_frame)
        self._commit_panned_film_strip_frame(current_animation, current_frame)

        # Update the film strip to reflect the pixel data changes
        self.film_strip_coordinator.update_film_strips_for_animated_sprite_update()
        self.log.debug('Updated film strip for frame %s[%s]', current_animation, current_frame)

        # Keep the panning state active so user can continue panning
        # Don't clear _original_frame_pixels, pan_offset_x, pan_offset_y, or _panning_active
        # The viewport will continue to show the panned view

        self.log.debug('Panned buffer committed, panning state preserved for continued panning')

    def _handle_film_strip_text_input(self, event: events.HashableEvent) -> bool | None:
        """Handle text input for film strips in text editing mode.

        Args:
            event: The key down event.

        Returns:
            True if escape was pressed (consume event), None if handled but not escape,
            or False if no film strip was in editing mode.

        """
        if not hasattr(self, 'film_strips'):
            return False

        for film_strip in self.film_strips.values():
            if (
                hasattr(film_strip, 'editing_animation')
                and film_strip.editing_animation
                and film_strip.handle_keyboard_input(event)
            ):
                # If escape was pressed, consume the event to prevent game quit
                if event.key == pygame.K_ESCAPE:
                    return True
                return None
        return False

    def _handle_ctrl_key_shortcuts(self, event: events.HashableEvent, mod: int) -> bool:  # noqa: PLR0911
        """Handle Ctrl-based keyboard shortcuts (undo, redo, copy, paste, panning).

        Args:
            event: The key down event.
            mod: The modifier key bitmask.

        Returns:
            True if the event was handled, False otherwise.

        """
        if not (mod & pygame.KMOD_CTRL):
            return False

        if event.key == pygame.K_z:
            if mod & pygame.KMOD_SHIFT:
                self.log.debug('Ctrl+Shift+Z pressed - redo')
                self.handle_redo()
            else:
                self.log.debug('Ctrl+Z pressed - undo')
                self.handle_undo()
            return True

        if event.key == pygame.K_y:
            self.log.debug('Ctrl+Y pressed - redo')
            self.handle_redo()
            return True

        if event.key == pygame.K_c:
            self.log.debug('Ctrl+C pressed - copying frame')
            self._handle_copy_frame()
            return True

        if event.key == pygame.K_v:
            self.log.debug('Ctrl+V pressed - pasting frame')
            self._handle_paste_frame()
            return True

        # Handle panning with Ctrl+Shift+Arrow keys
        if (mod & pygame.KMOD_SHIFT) and hasattr(self, 'canvas') and self.canvas:
            panning_map = {
                pygame.K_LEFT: (-1, 0, 'LEFT'),
                pygame.K_RIGHT: (1, 0, 'RIGHT'),
                pygame.K_UP: (0, -1, 'UP'),
                pygame.K_DOWN: (0, 1, 'DOWN'),
            }
            if event.key in panning_map:
                delta_x, delta_y, direction = panning_map[event.key]
                self.log.debug(
                    f'Ctrl+Shift+{direction} arrow pressed - panning {direction.lower()}',
                )
                self._handle_canvas_panning(delta_x, delta_y)
                return True

        return False

    def _handle_arrow_key_navigation(self, event: events.HashableEvent) -> bool:
        """Handle UP/DOWN arrow keys for animation navigation.

        Args:
            event: The key down event.

        Returns:
            True if the event was handled, False otherwise.

        """
        if event.key == pygame.K_UP:
            self.log.debug('UP arrow pressed - navigating to previous animation')
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.previous_animation()
                self.film_strip_coordinator.scroll_to_current_animation()
            return True

        if event.key == pygame.K_DOWN:
            self.log.debug('DOWN arrow pressed - navigating to next animation')
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.next_animation()
                self.film_strip_coordinator.scroll_to_current_animation()
            return True

        return False

    def _route_to_canvas_or_parent(self, event: events.HashableEvent) -> None:
        """Route keyboard event to canvas or fall back to parent handler.

        Args:
            event: The key down event.

        """
        # Check if any film strip is in text editing mode before routing to canvas
        if hasattr(self, 'film_strips'):
            for film_strip in self.film_strips.values():
                if hasattr(film_strip, 'editing_animation') and film_strip.editing_animation:
                    return

        if hasattr(self, 'canvas') and hasattr(self.canvas, 'handle_keyboard_event'):
            self.log.debug('Routing keyboard event to canvas')
            self.canvas.handle_keyboard_event(event.key)
        else:
            # Fall back to parent class handling
            self.log.debug('No canvas found, using parent class handling')
            super().on_key_down_event(event)

    @override
    def on_key_down_event(self, event: events.HashableEvent) -> None:
        """Handle keyboard events for frame navigation and text input."""
        self.log.debug(f'Key down event received: key={event.key}')

        # Check if debug text box is active and handle text input
        if hasattr(self, 'debug_text') and self.debug_text.active:
            self.debug_text.on_key_down_event(event)
            return

        # Check if any slider text box is active and handle text input
        slider_result = self._slider_manager.handle_slider_text_input(event)
        if slider_result is not False:
            return

        # Check if any film strip is in text editing mode and handle text input
        film_strip_result = self._handle_film_strip_text_input(event)
        if film_strip_result is not False:
            return

        # Handle onion skinning toggle, ctrl shortcuts, slider navigation,
        # arrow keys, or route to canvas
        self._handle_key_down_actions(event)

    def _handle_key_down_actions(self, event: events.HashableEvent) -> None:
        """Handle remaining key-down actions after text input checks.

        Args:
            event: The key down event.

        """
        # Handle onion skinning keyboard shortcuts
        if event.key == pygame.K_o:
            self.log.debug('O key pressed - toggling global onion skinning')
            from .onion_skinning import get_onion_skinning_manager

            onion_manager = get_onion_skinning_manager()
            new_state = onion_manager.toggle_global_onion_skinning()
            self.log.debug(f'Onion skinning {"enabled" if new_state else "disabled"}')
            # Force canvas redraw to show/hide onion skinning
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.force_redraw()
            return

        # Handle undo/redo and Ctrl-based keyboard shortcuts
        mod = getattr(event, 'mod', 0)
        if self._handle_ctrl_key_shortcuts(event, mod):
            return

        # Handle slider mode navigation with arrow keys
        if self._slider_manager.is_any_controller_in_slider_mode():
            if event.key == pygame.K_UP:
                self.log.debug('UP arrow pressed - navigating to previous slider mode')
                self.controller_handler.handle_slider_mode_navigation('up')
            elif event.key == pygame.K_DOWN:
                self.log.debug('DOWN arrow pressed - navigating to next slider mode')
                self.controller_handler.handle_slider_mode_navigation('down')
            return

        # Handle animation navigation and film strip scrolling (UP/DOWN arrows)
        if self._handle_arrow_key_navigation(event):
            return

        # Route to canvas or parent (only if not in slider mode)
        if not self._slider_manager.is_any_controller_in_slider_mode():
            self._route_to_canvas_or_parent(event)

    def handle_undo(self) -> None:
        """Handle undo operation."""
        if not hasattr(self, 'undo_redo_manager'):
            self.log.warning('Undo/redo manager not initialized')
            return

        # Get current frame information
        current_animation = None
        current_frame = None
        if hasattr(self, 'canvas') and self.canvas:
            current_animation = getattr(self.canvas, 'current_animation', None)
            current_frame = getattr(self.canvas, 'current_frame', None)

        # Try frame-specific undo first if we have a current frame
        if current_animation is not None and current_frame is not None:
            if self.undo_redo_manager.can_undo_frame(current_animation, current_frame):
                success = self.undo_redo_manager.undo_frame(current_animation, current_frame)
                if success:
                    self.log.info(
                        'Frame-specific undo successful for %s[%s]',
                        current_animation,
                        current_frame,
                    )
                    # Force canvas redraw to show the undone changes
                    if hasattr(self, 'canvas') and self.canvas:
                        self.canvas.force_redraw()
                    return
                self.log.warning(
                    'Frame-specific undo failed for %s[%s]',
                    current_animation,
                    current_frame,
                )
            else:
                self.log.warning('No frame-specific undo operations available')

        # Fall back to global undo for film strip operations
        if self.undo_redo_manager.can_undo():
            success = self.undo_redo_manager.undo()
            if success:
                self.log.info('Global undo successful')

                # CRITICAL: Ensure canvas state is valid after film strip operations
                self._synchronize_canvas_state_after_undo()

                # Force canvas redraw to show the undone changes
                if hasattr(self, 'canvas') and self.canvas:
                    self.canvas.force_redraw()
            else:
                self.log.warning('Global undo failed')
        else:
            self.log.debug('No operations available to undo')

    def _synchronize_canvas_state_after_undo(self) -> None:
        """Synchronize canvas state after undo operations to prevent invalid states.

        This method ensures that:
        1. The canvas is pointing to a valid animation
        2. The canvas is pointing to a valid frame index
        3. The canvas state is consistent with the current animation structure
        """
        if not hasattr(self, 'canvas') or not self.canvas:
            self.log.warning('No canvas available for state synchronization')
            return

        if not hasattr(self.canvas, 'animated_sprite') or not self.canvas.animated_sprite:
            self.log.warning('No animated sprite available for state synchronization')
            return

        animations = self.canvas.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        current_animation = getattr(self.canvas, 'current_animation', None)
        current_frame = getattr(self.canvas, 'current_frame', None)

        self.log.debug(
            'Canvas state before sync: animation=%s, frame=%s',
            current_animation,
            current_frame,
        )
        self.log.debug(f'Available animations: {list(animations.keys())}')

        # Check if current animation still exists
        if current_animation not in animations:
            self.log.warning(
                "Current animation '%s' no longer exists, switching to first available",
                current_animation,
            )
            if animations:
                # Switch to the first available animation
                first_animation = next(iter(animations.keys()))
                self.canvas.show_frame(first_animation, 0)
                self.log.info("Switched to animation '%s', frame 0", first_animation)
                return
            self.log.error('No animations available - this should not happen')
            return

        # Check if current frame index is valid
        frames = animations[current_animation]
        if current_frame is None or current_frame < 0 or current_frame >= len(frames):
            self.log.warning(
                f"Current frame {current_frame} is invalid for animation '{current_animation}' with"
                f' {len(frames)} frames',
            )
            # Switch to the last valid frame
            valid_frame = max(0, len(frames) - 1)
            self.canvas.show_frame(current_animation, valid_frame)
            self.log.info("Switched to frame %s of animation '%s'", valid_frame, current_animation)
            return

        # If we get here, the canvas state is valid
        self.log.debug(
            "Canvas state is valid: animation='%s', frame=%s",
            current_animation,
            current_frame,
        )

        # Force a complete canvas refresh to ensure everything is in sync
        self.canvas.force_redraw()

        # Update film strips to reflect the current state
        if hasattr(self, 'update_film_strips_for_frame'):
            self.film_strip_coordinator.update_film_strips_for_frame(
                current_animation,
                current_frame,
            )

    def handle_redo(self) -> None:
        """Handle redo operation."""
        if not hasattr(self, 'undo_redo_manager'):
            self.log.warning('Undo/redo manager not initialized')
            return

        # Get current frame information
        current_animation = None
        current_frame = None
        if hasattr(self, 'canvas') and self.canvas:
            current_animation = getattr(self.canvas, 'current_animation', None)
            current_frame = getattr(self.canvas, 'current_frame', None)

        # Try frame-specific redo first if we have a current frame
        if current_animation is not None and current_frame is not None:
            if self.undo_redo_manager.can_redo_frame(current_animation, current_frame):
                success = self.undo_redo_manager.redo_frame(current_animation, current_frame)
                if success:
                    self.log.info(
                        'Frame-specific redo successful for %s[%s]',
                        current_animation,
                        current_frame,
                    )
                    # Force canvas redraw to show the redone changes
                    if hasattr(self, 'canvas') and self.canvas:
                        self.canvas.force_redraw()
                    return
                self.log.warning(
                    'Frame-specific redo failed for %s[%s]',
                    current_animation,
                    current_frame,
                )
            else:
                self.log.warning('No frame-specific redo operations available')

        # Fall back to global redo for film strip operations
        if self.undo_redo_manager.can_redo():
            success = self.undo_redo_manager.redo()
            if success:
                self.log.info('Global redo successful')

                # CRITICAL: Ensure canvas state is valid after film strip operations
                self._synchronize_canvas_state_after_undo()

                # Force canvas redraw to show the redone changes
                if hasattr(self, 'canvas') and self.canvas:
                    self.canvas.force_redraw()
            else:
                self.log.warning('Global redo failed')
        else:
            self.log.debug('No operations available to redo')

    def _handle_canvas_panning(self, delta_x: int, delta_y: int) -> None:
        """Handle canvas panning with the given delta values.

        Args:
            delta_x: Horizontal panning delta (-1, 0, or 1)
            delta_y: Vertical panning delta (-1, 0, or 1)

        """
        if not hasattr(self, 'canvas') or not self.canvas:
            self.log.warning('No canvas available for panning')
            return

        # Delegate to canvas panning method
        if hasattr(self.canvas, 'pan_canvas'):
            self.canvas.pan_canvas(delta_x, delta_y)
        else:
            self.log.warning('Canvas does not support panning')

    def _handle_copy_frame(self) -> None:
        """Handle copying the current frame to clipboard."""
        if not hasattr(self, 'canvas') or not self.canvas:
            self.log.warning('No canvas available for frame copying')
            return

        if not hasattr(self, 'selected_animation') or not hasattr(self, 'selected_frame'):
            self.log.warning('No frame selected for copying')
            return

        animation = self.selected_animation
        frame = self.selected_frame

        if animation is None or frame is None:
            self.log.warning('No animation or frame selected for copying')
            return

        if not hasattr(self.canvas, 'animated_sprite') or not self.canvas.animated_sprite:
            self.log.warning('No animated sprite available for frame copying')
            return

        # Get the frame data
        if animation not in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            self.log.warning("Animation '%s' not found for copying", animation)
            return

        frames = self.canvas.animated_sprite._animations[animation]  # type: ignore[reportPrivateUsage]
        if frame >= len(frames):
            self.log.warning("Frame %s not found in animation '%s'", frame, animation)
            return

        frame_obj = frames[frame]

        # Create a deep copy of the frame data for the clipboard

        # Get pixel data
        pixels = frame_obj.get_pixel_data()

        # Get frame dimensions
        width, height = frame_obj.get_size()

        # Get frame duration
        duration = frame_obj.duration

        # Store frame data in clipboard
        self._frame_clipboard = {
            'pixels': pixels.copy(),
            'width': width,
            'height': height,
            'duration': duration,
            'animation': animation,
            'frame': frame,
        }

        self.log.debug("Copied frame %s from animation '%s' to clipboard", frame, animation)

    def _handle_paste_frame(self) -> None:  # noqa: PLR0911
        """Handle pasting a frame from clipboard to the current frame."""
        if not hasattr(self, 'canvas') or not self.canvas:
            self.log.warning('No canvas available for frame pasting')
            return

        if not hasattr(self, 'selected_animation') or not hasattr(self, 'selected_frame'):
            self.log.warning('No frame selected for pasting')
            return

        if not self._frame_clipboard:
            self.log.warning('No frame data in clipboard to paste')
            return

        animation = self.selected_animation
        frame = self.selected_frame

        if animation is None or frame is None:
            self.log.warning('No animation or frame selected for pasting')
            return

        if not hasattr(self.canvas, 'animated_sprite') or not self.canvas.animated_sprite:
            self.log.warning('No animated sprite available for frame pasting')
            return

        # Get the target frame
        if animation not in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            self.log.warning("Animation '%s' not found for pasting", animation)
            return

        frames = self.canvas.animated_sprite._animations[animation]  # type: ignore[reportPrivateUsage]
        if frame >= len(frames):
            self.log.warning("Frame %s not found in animation '%s'", frame, animation)
            return

        target_frame = frames[frame]

        # Check if dimensions match
        clipboard_width = self._frame_clipboard['width']
        clipboard_height = self._frame_clipboard['height']
        target_width, target_height = target_frame.get_size()

        if clipboard_width != target_width or clipboard_height != target_height:
            self.log.warning(
                'Cannot paste frame: dimension mismatch (clipboard: %sx%s, target: %sx%s)',
                clipboard_width,
                clipboard_height,
                target_width,
                target_height,
            )
            return

        # Store original frame data for undo
        original_pixels = target_frame.get_pixel_data()
        original_duration = target_frame.duration

        # Create and execute a FramePasteCommand
        paste_command = FramePasteCommand(
            editor=self,
            animation=animation,
            frame=frame,
            old_pixels=original_pixels,
            old_duration=original_duration,
            new_pixels=self._frame_clipboard['pixels'],
            new_duration=self._frame_clipboard['duration'],
        )
        paste_command.execute()

        # Push onto the undo stack
        self.undo_redo_manager.push_command(paste_command)

        # Update canvas display
        if hasattr(self.canvas, 'force_redraw'):
            self.canvas.force_redraw()

        self.log.debug('Pasted frame from clipboard to %s[%s]', animation, frame)

    def _submit_pixel_changes_if_ready(self) -> None:
        """Submit collected pixel changes if they're ready (single click or drag ended)."""
        # Convert dict to list format for submission (dict is used for efficient O(1) deduplication
        # during drag)
        pixel_changes_list = []
        if hasattr(self, 'current_pixel_changes_dict') and self.current_pixel_changes_dict:
            # Convert dict values to list format
            pixel_changes_list = list(self.current_pixel_changes_dict.values())
            # Clear the dict after conversion
            self.current_pixel_changes_dict.clear()
        elif hasattr(self, 'current_pixel_changes') and self.current_pixel_changes:
            # Fallback to list if dict doesn't exist (backward compatibility)
            pixel_changes_list = self.current_pixel_changes

        if pixel_changes_list and hasattr(self, 'canvas_operation_tracker'):
            pixel_count = len(pixel_changes_list)

            # Get current frame information for frame-specific tracking
            current_animation = None
            current_frame = None
            if hasattr(self, 'canvas') and self.canvas:
                current_animation = getattr(self.canvas, 'current_animation', None)
                current_frame = getattr(self.canvas, 'current_frame', None)

            # Use frame-specific tracking if we have frame information
            if current_animation is not None and current_frame is not None:
                self.canvas_operation_tracker.add_frame_pixel_changes(
                    current_animation,
                    current_frame,
                    pixel_changes_list,  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
                )
                self.log.debug(
                    'Submitted %s pixel changes for frame %s[%s] undo/redo tracking',
                    pixel_count,
                    current_animation,
                    current_frame,
                )
            else:
                # Fall back to global tracking
                self.canvas_operation_tracker.add_pixel_changes(pixel_changes_list)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
                self.log.debug(
                    'Submitted %s pixel changes for global undo/redo tracking',
                    pixel_count,
                )

            # Clear both collections after submission
            if hasattr(self, 'current_pixel_changes'):
                self.current_pixel_changes = []
            if hasattr(self, 'current_pixel_changes_dict'):
                self.current_pixel_changes_dict.clear()

    def _check_single_click_timer(self) -> None:
        """Check if we should submit a single click based on timer."""
        # Check dict first (new optimized path), then fallback to list
        pixel_count = 0
        if hasattr(self, 'current_pixel_changes_dict') and self.current_pixel_changes_dict:
            pixel_count = len(self.current_pixel_changes_dict)
        elif hasattr(self, 'current_pixel_changes') and self.current_pixel_changes:
            pixel_count = len(self.current_pixel_changes)

        if (
            pixel_count == 1  # Only for single pixels
            and hasattr(self, '_pixel_change_timer')
            and self._pixel_change_timer
        ):
            import time

            current_time = time.time()
            # If more than 0.1 seconds have passed since the first pixel change, submit it
            if current_time - self._pixel_change_timer > PIXEL_CHANGE_DEBOUNCE_SECONDS:
                self._submit_pixel_changes_if_ready()
                self._pixel_change_timer = None

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> None:
        """Add command line arguments.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Raises:
            None

        """
        parser.add_argument(
            '-v',
            '--version',
            action='store_true',
            help='print the game version and exit',
        )
        parser.add_argument('-s', '--size', default='32x32')

    @override
    def _handle_scene_key_events(self, event: events.HashableEvent) -> None:
        """Handle scene-level key events."""
        self.log.debug(f'Scene-level key event: {event.key}')

        # Call our custom keyboard handler
        self.on_key_down_event(event)

    @override
    def on_drop_file_event(self, event: events.HashableEvent) -> None:
        """Handle drop file event by delegating to FileIOManager."""
        self._file_io.on_drop_file_event(event)

    def handle_event(self, event: events.HashableEvent) -> None:
        """Handle pygame events."""
        # Debug logging for keyboard events
        if event.type == pygame.KEYDOWN:
            self.log.debug(f'KEYDOWN event received in handle_event: key={event.key}')

        # Handle confirmation dialog clicks first (highest priority)
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and hasattr(self, 'confirmation_dialog')
            and self.confirmation_dialog
        ):
            mouse_pos = pygame.mouse.get_pos()
            if self.confirmation_dialog.rect.collidepoint(mouse_pos):
                # Convert to dialog-relative coordinates
                dialog_relative_pos = (
                    mouse_pos[0] - self.confirmation_dialog.rect.x,
                    mouse_pos[1] - self.confirmation_dialog.rect.y,
                )
                if self.confirmation_dialog.handle_mouse_down(dialog_relative_pos):
                    self.confirmation_dialog = None  # Clear reference after handling
                    return  # Event handled, don't pass to other handlers

        super().handle_event(event)  # type: ignore[arg-type] # ty: ignore[unresolved-attribute]

        if event.type == pygame.WINDOWLEAVE:
            # Notify sprites that mouse left window
            for sprite in self.all_sprites:
                if hasattr(sprite, 'on_mouse_leave_window_event'):
                    sprite.on_mouse_leave_window_event(event)

    def deflate(self: Self) -> dict[str, Any]:
        """Deflate a sprite to a Bitmappy config file.

        Returns:
            dict: The result.

        Raises:
            StopIteration: If the RGB triplet generator produces no data.

        """
        try:
            self.log.debug(f'Starting deflate for {self.name}')
            self.log.debug(f'Image dimensions: {self.image.get_size()}')

            # Note: This deflate method is incomplete - configparser was removed
            # as we only support TOML format now. This needs to be reimplemented
            # to generate TOML output using the toml library.
            config: dict[str, Any] = {}

            # Get the raw pixel data and log its size
            pixel_string = pygame.image.tobytes(self.image, 'RGB')
            self.log.debug(f'Raw pixel string length: {len(pixel_string)}')

            # Log the first few bytes of pixel data
            self.log.debug(f'First 12 bytes of pixel data: {list(pixel_string[:12])}')

            # Create the generator and log initial state
            raw_pixels = rgb_triplet_generator(pixel_data=pixel_string)
            self.log.debug('Created RGB triplet generator')

            # Try to get the first triplet
            try:
                first_triplet = next(raw_pixels)
                self.log.debug('First RGB triplet: %s', first_triplet)
                # Reset generator
                raw_pixels = rgb_triplet_generator(pixel_data=pixel_string)
            except StopIteration:
                self.log.exception('Generator empty on first triplet!')
                raise

            # Now proceed with the rest of deflate
            raw_pixels = list(raw_pixels)
            self.log.debug(f'Converted {len(raw_pixels)} RGB triplets to list')

            # Continue with original deflate code...
            colors = set(raw_pixels)
            self.log.debug(f'Found {len(colors)} unique colors')

        except Exception:
            self.log.exception('Error in deflate')
            raise
        else:
            return config

    # ──────────────────────────────────────────────────────────────────────
    # Film strip delegation (methods extracted to film_strip_coordinator.py)
    # These satisfy the EditorContext protocol so other subsystems can call them.
    # ──────────────────────────────────────────────────────────────────────

    def update_film_strip_visibility(self) -> None:
        """Delegate to FilmStripCoordinator."""
        self.film_strip_coordinator.update_film_strip_visibility()

    def update_scroll_arrows(self) -> None:
        """Delegate to FilmStripCoordinator."""
        self.film_strip_coordinator.update_scroll_arrows()

    def on_film_strip_frame_selected(
        self,
        film_strip_widget: FilmStripWidget,
        animation: str,
        frame: int,
    ) -> None:
        """Delegate to FilmStripCoordinator."""
        self.film_strip_coordinator.on_film_strip_frame_selected(
            film_strip_widget,
            animation,
            frame,
        )

    def update_film_strip_selection_state(self) -> None:
        """Delegate to FilmStripCoordinator."""
        self.film_strip_coordinator.update_film_strip_selection_state()

    def on_animation_rename(self, old_name: str, new_name: str) -> None:
        """Delegate to FilmStripCoordinator."""
        self.film_strip_coordinator.on_animation_rename(old_name, new_name)

    def scroll_film_strips_up(self) -> None:
        """Delegate to FilmStripCoordinator."""
        self.film_strip_coordinator.scroll_film_strips_up()

    def scroll_film_strips_down(self) -> None:
        """Delegate to FilmStripCoordinator."""
        self.film_strip_coordinator.scroll_film_strips_down()

    # ──────────────────────────────────────────────────────────────────────
    # Color state methods (used by both keyboard and controller handlers)
    # ──────────────────────────────────────────────────────────────────────

    def get_current_color(self) -> tuple[int, ...]:
        """Get the current color by delegating to SliderManager.

        Returns:
            tuple: The current color from the sliders.

        """
        return self._slider_manager.get_current_color()

    def update_color_well_from_sliders(self) -> None:
        """Update the color well by delegating to SliderManager."""
        self._slider_manager.update_color_well_from_sliders()

    # ──────────────────────────────────────────────────────────────────────
    # Controller event delegation (methods extracted to controllers/event_handler.py)
    # ──────────────────────────────────────────────────────────────────────

    @override
    def on_controller_button_down_event(self, event: events.HashableEvent) -> None:
        """Handle controller button down events by delegating to ControllerEventHandler."""
        self.controller_handler.on_controller_button_down_event(event)

    @override
    def on_controller_button_up_event(self, event: events.HashableEvent) -> None:
        """Handle controller button up events by delegating to ControllerEventHandler."""
        self.controller_handler.on_controller_button_up_event(event)

    @override
    def on_joy_button_down_event(self, event: events.HashableEvent) -> None:
        """Handle joystick button down events by delegating to ControllerEventHandler."""
        self.controller_handler.on_joy_button_down_event(event)

    @override
    def on_joy_button_up_event(self, event: events.HashableEvent) -> None:
        """Handle joystick button up events by delegating to ControllerEventHandler."""
        self.controller_handler.on_joy_button_up_event(event)

    @override
    def on_joy_hat_motion_event(self, event: events.HashableEvent) -> None:
        """Handle joystick hat motion events by delegating to ControllerEventHandler."""
        self.controller_handler.on_joy_hat_motion_event(event)

    @override
    def on_joy_axis_motion_event(self, event: events.HashableEvent) -> None:
        """Handle joystick axis motion events by delegating to ControllerEventHandler."""
        self.controller_handler.on_joy_axis_motion_event(event)

    @override
    def on_joy_ball_motion_event(self, event: events.HashableEvent) -> None:
        """Handle joystick ball motion events by delegating to ControllerEventHandler."""
        self.controller_handler.on_joy_ball_motion_event(event)

    @override
    def on_controller_axis_motion_event(self, event: events.HashableEvent) -> None:
        """Handle controller axis motion events by delegating to ControllerEventHandler."""
        self.controller_handler.on_controller_axis_motion_event(event)


def main() -> None:
    """Run the main function.

    Raises:
        None

    """
    LOG.setLevel(logging.INFO)

    # Set up signal handling to prevent multiprocessing issues on macOS
    def signal_handler(signum: int, _frame: types.FrameType | None) -> None:
        """Handle shutdown signals gracefully."""
        LOG.info(f'Received signal {signum}, shutting down gracefully...')
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Set multiprocessing start method to avoid macOS issues
    with contextlib.suppress(RuntimeError):
        multiprocessing.set_start_method('spawn', force=True)

    icon_path = Path(__file__).parent / 'resources' / 'bitmappy.png'

    # Initialize the game engine first to set up display
    engine = GameEngine(game=BitmapEditorScene, icon=icon_path)

    # Load AI training data after engine initialization
    load_ai_training_data()

    # Start the engine
    engine.start()


if __name__ == '__main__':
    main()
