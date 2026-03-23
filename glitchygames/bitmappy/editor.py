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
    MAX_COLOR_CHANNEL_VALUE,
    RGBA_COMPONENT_COUNT,
)
from glitchygames.engine import GameEngine
from glitchygames.pixels import rgb_triplet_generator
from glitchygames.scenes import Scene
from glitchygames.sprites import (
    BitmappySprite,
)
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
    MAX_COLOR_VALUE,
    MIN_COLOR_VALUE,
    MIN_FILM_STRIPS_FOR_PANEL_POSITIONING,
    MIN_PIXEL_DISPLAY_SIZE,
    PIXEL_CHANGE_DEBOUNCE_SECONDS,
)
from .controller_handler import ControllerEventHandler
from .controllers.manager import MultiControllerManager
from .file_io import FileIOManager
from .film_strip_coordinator import FilmStripCoordinator
from .history.operations import (
    CanvasOperationTracker,
    CrossAreaOperationTracker,
    FilmStripOperationTracker,
)
from .history.undo_redo import UndoRedoManager
from .indicators.collision import VisualCollisionManager
from .sprite_inspection import load_ai_training_data
from .utils import resource_path

if TYPE_CHECKING:
    import argparse

    from .controllers.selection import ControllerSelection
    from .film_strip import FilmStripWidget
    from .film_strip_sprite import FilmStripSprite
    from .scroll_arrow import ScrollArrowSprite


class BitmapEditorScene(Scene):
    """Bitmap Editor Scene.

    The scene expects a 'size' option in the format "WIDTHxHEIGHT" (e.g., "800x600")
    when initialized. This corresponds to the -s command line parameter.
    """

    log = LOG

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
            f' {pixels_across}x{pixels_tall}'
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
        self, animated_sprite: AnimatedSprite, pixels_across: int, pixels_tall: int, pixel_size: int
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
            f'({self.canvas.rect.x}, {self.canvas.rect.y}) with size {self.canvas.rect.size}'
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

    def _setup_sliders_and_color_well(self) -> None:
        """Set up the color sliders and color well."""
        # First create the sliders
        slider_height = 9
        slider_width = 256
        slider_x = 13  # Moved 3 pixels to the right
        label_padding = 10  # Padding between slider and label
        well_padding = 20  # Padding between labels and color well

        # Create the sliders - positioned so blue slider bottom touches screen bottom
        # Account for bounding box height (slider_height + 4) in positioning
        # Blue slider bottom should be at screen_height - 2 (one pixel up from last visible row)
        bbox_height = slider_height + 4
        blue_slider_y = self.screen_height - slider_height - 2  # Bottom edge at screen_height - 2
        green_slider_y = blue_slider_y - bbox_height  # Use bounding box height for spacing
        red_slider_y = green_slider_y - bbox_height  # Use bounding box height for spacing
        alpha_slider_y = red_slider_y - bbox_height  # Alpha slider above red slider

        slider_y_positions = {
            'alpha': alpha_slider_y,
            'red': red_slider_y,
            'green': green_slider_y,
            'blue': blue_slider_y,
        }

        self._create_slider_labels(
            slider_x=slider_x,
            slider_height=slider_height,
            slider_y_positions=slider_y_positions,
        )

        self._create_slider_sprites(
            slider_x=slider_x,
            slider_width=slider_width,
            slider_height=slider_height,
            slider_y_positions=slider_y_positions,
        )

        self._create_slider_bounding_boxes(
            slider_x=slider_x,
            slider_width=slider_width,
            slider_height=slider_height,
            slider_y_positions=slider_y_positions,
        )

        # Create the color well positioned to the right of the text labels
        # Calculate x position to the right of the text labels
        # Text labels are at: slider_x + slider_width + label_padding
        text_label_x = slider_x + slider_width + label_padding
        color_well_x = text_label_x + well_padding  # Add padding after text labels

        self._create_color_well_and_tab_control(
            color_well_x=color_well_x,
            red_slider_y=red_slider_y,
            blue_slider_y=blue_slider_y,
            slider_height=slider_height,
        )

        self._configure_slider_text_boxes(
            text_label_x=text_label_x,
            color_well_x=color_well_x,
        )

        self._initialize_slider_values()

    def _create_slider_labels(
        self,
        *,
        slider_x: int,
        slider_height: int,
        slider_y_positions: dict[str, int],
    ) -> None:
        """Create text labels for each color slider.

        Args:
            slider_x: X position of sliders
            slider_height: Height of each slider
            slider_y_positions: Dict mapping color names to Y positions

        """
        # Create text labels for each slider
        label_x = (
            slider_x - 13
        )  # Position labels to the left of sliders (moved 7 pixels right total)
        label_width = 16  # Width for text labels
        label_height = 16  # Height for text labels

        from glitchygames.fonts import FontManager

        monospace_config = {'font_name': 'Courier', 'font_size': 14}

        # Alpha slider label
        self.alpha_label = TextSprite(
            text='A',
            x=label_x - 2,  # Move A label 2 pixels left (same as R and G)
            y=slider_y_positions['alpha'] + (slider_height - label_height) // 2,
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.all_sprites,
        )
        # Set monospaced font for the label
        self.alpha_label.font = FontManager.get_font(font_config=monospace_config)  # type: ignore[assignment]

        # Red slider label
        self.red_label = TextSprite(
            text='R',
            x=label_x - 2,  # Move R label 2 pixels left
            y=slider_y_positions['red'] + (slider_height - label_height) // 2,
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.all_sprites,
        )
        # Set monospaced font for the label
        self.red_label.font = FontManager.get_font(font_config=monospace_config)  # type: ignore[assignment]

        # Green slider label
        self.green_label = TextSprite(
            text='G',
            x=label_x - 2,  # Move G label 2 pixels left
            y=slider_y_positions['green'] + (slider_height - label_height) // 2,
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.all_sprites,
        )
        # Set monospaced font for the label
        self.green_label.font = FontManager.get_font(font_config=monospace_config)  # type: ignore[assignment]

        # Blue slider label
        self.blue_label = TextSprite(
            text='B',
            x=label_x - 1,  # Adjust B label 1 pixel left to align with R and G
            y=slider_y_positions['blue'] + (slider_height - label_height) // 2,
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.all_sprites,
        )
        # Set monospaced font for the label
        self.blue_label.font = FontManager.get_font(font_config=monospace_config)  # type: ignore[assignment]

    def _create_slider_sprites(
        self,
        *,
        slider_x: int,
        slider_width: int,
        slider_height: int,
        slider_y_positions: dict[str, int],
    ) -> None:
        """Create the ARGB slider sprites.

        Args:
            slider_x: X position of sliders
            slider_width: Width of each slider
            slider_height: Height of each slider
            slider_y_positions: Dict mapping color names to Y positions

        """
        self.alpha_slider = SliderSprite(
            name='A',
            x=slider_x,
            y=slider_y_positions['alpha'],
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        self.red_slider = SliderSprite(
            name='R',
            x=slider_x,
            y=slider_y_positions['red'],
            width=slider_width,
            height=slider_height,
            parent=self,  # type: ignore[reportArgumentType]  # BitmapEditorScene satisfies SliderProtocol at runtime
            groups=self.all_sprites,
        )

        self.green_slider = SliderSprite(
            name='G',
            x=slider_x,
            y=slider_y_positions['green'],
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        self.blue_slider = SliderSprite(
            name='B',
            x=slider_x,
            y=slider_y_positions['blue'],
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

    def _create_slider_bounding_boxes(
        self,
        *,
        slider_x: int,
        slider_width: int,
        slider_height: int,
        slider_y_positions: dict[str, int],
    ) -> None:
        """Create bounding boxes around the sliders for hover effects (initially hidden).

        Args:
            slider_x: X position of sliders
            slider_width: Width of each slider
            slider_height: Height of each slider
            slider_y_positions: Dict mapping color names to Y positions

        """
        bbox_configs = [
            ('alpha_slider_bbox', 'Alpha Slider BBox', slider_y_positions['alpha']),
            ('red_slider_bbox', 'Red Slider BBox', slider_y_positions['red']),
            ('green_slider_bbox', 'Green Slider BBox', slider_y_positions['green']),
            ('blue_slider_bbox', 'Blue Slider BBox', slider_y_positions['blue']),
        ]

        for attr_name, bbox_name, bbox_y in bbox_configs:
            bbox_sprite = BitmappySprite(
                x=slider_x - 2,
                y=bbox_y - 2,
                width=slider_width + 4,
                height=slider_height + 4,
                name=bbox_name,
                groups=self.all_sprites,
            )
            # Create transparent surface (no border initially)
            bbox_sprite.image = pygame.Surface(
                (slider_width + 4, slider_height + 4), pygame.SRCALPHA
            )
            bbox_sprite.visible = False  # Start hidden
            # Update bounding box position to match slider position
            bbox_sprite.rect.y = bbox_y - 2
            setattr(self, attr_name, bbox_sprite)

    def _create_color_well_and_tab_control(
        self,
        *,
        color_well_x: int,
        red_slider_y: int,
        blue_slider_y: int,
        slider_height: int,
    ) -> None:
        """Create the color well and format tab control.

        Args:
            color_well_x: X position for the color well
            red_slider_y: Y position of the red slider
            blue_slider_y: Y position of the blue slider
            slider_height: Height of each slider

        """
        # Position colorwell so its top y matches R slider's top y
        # and its bottom y is shorter than blue slider's bottom y
        blue_slider_bottom_y = blue_slider_y + slider_height
        color_well_y = red_slider_y - 5  # Add some padding above
        color_well_height = (
            blue_slider_bottom_y - color_well_y
        ) + 2  # 2 pixels taller than B slider's bottom y

        # Calculate canvas right edge position
        if hasattr(self, 'canvas') and self.canvas:
            canvas_right_x = self.canvas.pixels_across * self.canvas.pixel_width
        else:
            # Fallback for tests or when canvas isn't initialized yet
            canvas_right_x = self.screen_width - 20
        # Set colorwell width so its right edge aligns with canvas right edge
        color_well_width = canvas_right_x - color_well_x
        # Ensure minimum width to prevent invalid surface creation
        color_well_width = max(color_well_width, 50)
        # Ensure minimum height to prevent invalid surface creation (reduced from 50)
        color_well_height = max(color_well_height, 20)

        self.color_well = ColorWellSprite(
            name='Color Well',
            x=color_well_x,
            y=color_well_y,  # Top y matches R slider's top y
            width=color_well_width,
            height=color_well_height,  # Height spans from R top to G bottom
            parent=self,
            groups=self.all_sprites,
        )

        # Create tab control positioned above the color well
        tab_control_width = color_well_width  # Match the color well width
        tab_control_height = 20
        tab_control_x = (
            color_well_x + (color_well_width - tab_control_width) // 2
        )  # Center horizontally
        tab_control_y = (
            color_well_y - tab_control_height
        )  # Position so bottom touches top of color well

        self.tab_control = TabControlSprite(
            name='Format Tab Control',
            x=tab_control_x,
            y=tab_control_y,
            width=tab_control_width,
            height=tab_control_height,
            parent=self,  # type: ignore[arg-type]  # BitmapEditorScene implements TabProtocol
            groups=self.all_sprites,
        )

    def _configure_slider_text_boxes(
        self,
        *,
        text_label_x: int,
        color_well_x: int,
    ) -> None:
        """Configure slider text box widths and heights to fit the layout.

        Args:
            text_label_x: X position of the text labels
            color_well_x: X position of the color well

        """
        # Initialize slider input format (default to decimal)
        self.slider_input_format = '%d'

        # Update text box widths to fit between slider end and color well start
        text_box_width = color_well_x - text_label_x + 4  # Make 4 pixels wider
        # Shrink text boxes vertically by 4 pixels
        text_box_height = 16  # Original was 20, now 16 (4 pixels smaller)

        for slider in (self.alpha_slider, self.red_slider, self.green_slider, self.blue_slider):
            slider.text_sprite.width = text_box_width
            slider.text_sprite.height = text_box_height
            # Force text sprites to update with new dimensions
            slider.text_sprite.update_text(slider.text_sprite.text)

    def _initialize_slider_values(self) -> None:
        """Initialize slider default values and sync with color well."""
        self.alpha_slider.value = 255
        self.red_slider.value = 0
        self.blue_slider.value = 0
        self.green_slider.value = 0

        self.color_well.active_color = (
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
            self.alpha_slider.value,
        )

        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.active_color = self.color_well.active_color  # type: ignore[assignment]

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
                    film_strip_list[1], 'rect'
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
                    film_strip_list[1], 'rect'
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
                    'clear the ai sprite box', self._clear_ai_sprite_box
                )
                self.voice_manager.register_command(
                    'clear ai sprite box', self._clear_ai_sprite_box
                )
                self.voice_manager.register_command('clear ai box', self._clear_ai_sprite_box)
                # Add commands for what speech recognition actually hears
                self.voice_manager.register_command(
                    'clear the ai sprite', self._clear_ai_sprite_box
                )
                self.voice_manager.register_command('clear ai sprite', self._clear_ai_sprite_box)
                # Add command for "window" variation
                self.voice_manager.register_command(
                    'clear the ai sprite window', self._clear_ai_sprite_box
                )
                self.voice_manager.register_command(
                    'clear ai sprite window', self._clear_ai_sprite_box
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

        # Slider bounding box sprites for hover effects (set dynamically in _create_slider_bboxes)
        self.alpha_slider_bbox: BitmappySprite | None = None
        self.red_slider_bbox: BitmappySprite | None = None
        self.green_slider_bbox: BitmappySprite | None = None
        self.blue_slider_bbox: BitmappySprite | None = None

        # Pixel change tracking dict for deduplication (used alongside _current_pixel_changes list)
        self.current_pixel_changes_dict: dict[
            int, tuple[int, tuple[int, ...], tuple[int, ...]]
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
        self.controller_handler = ControllerEventHandler(self)
        self.film_strip_coordinator = FilmStripCoordinator(self)

        # Set up all components
        self._setup_menu_bar()
        self._setup_canvas(options)
        self._setup_sliders_and_color_well()
        self._setup_debug_text_box()

        # Set up film strips after canvas is ready
        self.film_strip_coordinator.setup_film_strips()

        # Set up callback for when sprites are loaded
        if hasattr(self, 'canvas') and self.canvas:
            # Set up the callback on the canvas to call the main scene
            self.canvas.on_sprite_loaded = self.film_strip_coordinator.on_sprite_loaded  # type: ignore[attr-defined]
            self.log.debug('Set up on_sprite_loaded callback for canvas')
            LOG.debug('DEBUG: Set up on_sprite_loaded callback for canvas')

        # Controller selection will be initialized when START button is pressed

        # Query model capabilities for optimal token usage
        # try:
        #     capabilities = {
        #         "max_tokens": AI_MAX_INPUT_TOKENS,
        #         "context_size": AI_MAX_CONTEXT_SIZE
        #     }
        #     #capabilities = _get_model_capabilities(self.log)
        #     if capabilities.get("max_tokens"):
        #         self.log.info(f"Model max tokens detected: {capabilities['max_tokens']}")

        #         # Update AI_MAX_INPUT_TOKENS with detected capabilities
        #         global AI_MAX_INPUT_TOKENS
        #         old_max_tokens = AI_MAX_INPUT_TOKENS
        #         AI_MAX_INPUT_TOKENS = capabilities['max_tokens']
        #         self.log.info(f"Updated AI_MAX_INPUT_TOKENS from {old_max_tokens} to
        #         {AI_MAX_INPUT_TOKENS}")

        #         # Also log context size if available
        #         if capabilities.get("context_size"):
        #             self.log.info(f"Model context size: {capabilities['context_size']}")

        # except (ValueError, ConnectionError, TimeoutError) as e:
        #     self.log.warning(f"Could not query model capabilities: {e}")

        # Set up voice recognition
        # VOICE RECOGNITION IS CURRENTLY DISABLED
        # See _setup_voice_recognition() method documentation (line ~5382) for details
        # about why it's disabled and how to enable it in the future.
        #
        # To enable: Uncomment the following line after testing microphone access
        # and verifying speech recognition works reliably on your platform.
        # self._setup_voice_recognition()

        self.all_sprites.clear(self.screen, self.background)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

        # TODO: Plumb this into the scene manager

    def _init_undo_redo_system(self) -> None:
        """Initialize the undo/redo system with all operation trackers and callbacks."""
        self.undo_redo_manager = UndoRedoManager(max_history=50)
        self.canvas_operation_tracker = CanvasOperationTracker(self.undo_redo_manager)
        self.film_strip_operation_tracker = FilmStripOperationTracker(self.undo_redo_manager)
        self.cross_area_operation_tracker = CrossAreaOperationTracker(self.undo_redo_manager)
        from glitchygames.bitmappy.history.operations import ControllerPositionOperationTracker

        self.controller_position_operation_tracker = ControllerPositionOperationTracker(
            self.undo_redo_manager
        )

        self.undo_redo_manager.set_pixel_change_callback(self._apply_pixel_change_for_undo_redo)
        self.undo_redo_manager.set_film_strip_callbacks(
            add_frame_callback=self._add_frame_for_undo_redo,
            delete_frame_callback=self._delete_frame_for_undo_redo,
            reorder_frame_callback=self._reorder_frame_for_undo_redo,
            add_animation_callback=self._add_animation_for_undo_redo,
            delete_animation_callback=self._delete_animation_for_undo_redo,
        )
        self.undo_redo_manager.set_frame_selection_callback(
            self._apply_frame_selection_for_undo_redo
        )
        self.undo_redo_manager.set_controller_position_callback(
            self._apply_controller_position_for_undo_redo
        )
        self.undo_redo_manager.set_controller_mode_callback(
            self._apply_controller_mode_for_undo_redo
        )
        self.undo_redo_manager.set_frame_paste_callback(self._apply_frame_paste_for_undo_redo)

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
        self.log.info(f'Scene got menu item event: {event}')
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
        self.log.info(f'Creating new canvas with dimensions: {dimensions}')

        try:
            width, height = map(int, dimensions.lower().split('x'))
            self.log.info(f'Parsed dimensions: {width}x{height}')

            available_height = self.screen_height - 80 - 24
            new_pixel_size = min(
                available_height // height,
                (self.screen_width * 1 // 2) // width,
                350 // width,
            )
            self.log.info(f'Calculated new pixel size: {new_pixel_size}')

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
            self.log.info(f'Canvas resized to {width}x{height} with pixel size {new_pixel_size}')

        except ValueError:
            self.log.exception(f"Invalid dimensions format '{dimensions}'")
            self.log.exception("Expected format: WxH (e.g., '32x32')")

        self.dirty = 1

    def on_new_canvas_dialog_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the new canvas dialog event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        # Create a fresh dialog scene each time
        new_canvas_dialog_scene = NewCanvasDialogScene(options=self.options, previous_scene=self)
        # Set the dialog's background to the screenshot
        new_canvas_dialog_scene.background = self.screenshot
        self.next_scene = new_canvas_dialog_scene
        self.dirty = 1

    def on_load_dialog_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the load dialog event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        # Create a fresh dialog scene each time
        load_dialog_scene = LoadDialogScene(options=self.options, previous_scene=self)
        # Set the dialog's background to the screenshot
        load_dialog_scene.background = self.screenshot
        self.next_scene = load_dialog_scene
        self.dirty = 1

    def on_save_dialog_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the save dialog event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        # Create a fresh dialog scene each time
        save_dialog_scene = SaveDialogScene(options=self.options, previous_scene=self)
        # Set the dialog's background to the screenshot
        save_dialog_scene.background = self.screenshot
        self.next_scene = save_dialog_scene
        self.dirty = 1

    def on_color_well_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle the color well event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Raises:
            None

        """
        self.log.info('COLOR WELL EVENT')

    def _sample_color_from_screen(self, screen_pos: tuple[int, int]) -> None:
        """Sample color directly from the screen (RGB only, ignores alpha).

        Args:
            screen_pos: Screen coordinates (x, y) to sample from

        """
        try:
            # Sample directly from the screen
            assert self.screen is not None
            color = self.screen.get_at(screen_pos)

            # Handle both RGB and RGBA screen formats
            if len(color) == RGBA_COMPONENT_COUNT:
                red, green, blue, _ = color  # Ignore alpha from screen
            else:
                red, green, blue = color
            alpha = 255  # Screen has no meaningful alpha, default to opaque

            self.log.info(
                f'Screen pixel sampled - Red: {red}, Green: {green}, Blue: {blue}, Alpha: {alpha}'
                f' (default)'
            )

            # Update all sliders with the sampled RGB values and default alpha
            trigger = events.HashableEvent(0, name='R', value=red)
            self.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

            trigger = events.HashableEvent(0, name='G', value=green)
            self.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

            trigger = events.HashableEvent(0, name='B', value=blue)
            self.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

            trigger = events.HashableEvent(0, name='A', value=alpha)
            self.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

            self.log.info(
                f'Updated sliders with screen color R:{red}, G:{green}, B:{blue}, A:{alpha}'
            )

        except Exception:
            self.log.exception('Error sampling color from screen')

    def on_slider_event(
        self: Self, event: events.HashableEvent, trigger: events.HashableEvent
    ) -> None:
        """Handle the slider event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Raises:
            None

        """
        value = trigger.value

        self.log.debug(f'Slider: event: {event}, trigger: {trigger} value: {value}')

        if value < MIN_COLOR_VALUE:
            value = MIN_COLOR_VALUE
            trigger.value = MIN_COLOR_VALUE  # type: ignore[misc]
        elif value > MAX_COLOR_VALUE:
            value = MAX_COLOR_VALUE
            trigger.value = MAX_COLOR_VALUE  # type: ignore[misc]

        if trigger.name == 'R':
            self.red_slider.value = value
            self.log.debug(f'Updated red slider to: {value}')
        elif trigger.name == 'G':
            self.green_slider.value = value
            self.log.debug(f'Updated green slider to: {value}')
        elif trigger.name == 'B':
            self.blue_slider.value = value
            self.log.debug(f'Updated blue slider to: {value}')
        elif trigger.name == 'A':
            self.alpha_slider.value = value
            self.log.debug(f'Updated alpha slider to: {value}')

        # Update slider text to reflect current tab format
        # This handles slider clicks - text input is handled by SliderSprite itself
        self._update_slider_text_format()

        # Debug: Log current slider values
        self.log.debug(
            f'Current slider values - R: {self.red_slider.value}, '
            f'G: {self.green_slider.value}, B: {self.blue_slider.value}, A:'
            f' {self.alpha_slider.value}'
        )

        self.color_well.active_color = (
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
            self.alpha_slider.value,
        )
        self.canvas.active_color = (  # type: ignore[assignment]
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
            self.alpha_slider.value,
        )

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
        if (
            hasattr(self, 'canvas')
            and self.canvas
            and self.canvas.rect is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.canvas.rect.collidepoint(event.pos)
        ):
            if is_shift_click:
                # Shift-right-click: sample screen directly (RGB only)
                self.log.info('Shift-right-click detected on canvas - sampling screen directly')
                self._sample_color_from_screen(event.pos)
                return
            # Regular right-click: sample from canvas pixel data (RGBA)
            canvas_x = (event.pos[0] - self.canvas.rect.x) // self.canvas.pixel_width
            canvas_y = (event.pos[1] - self.canvas.rect.y) // self.canvas.pixel_height

            # Check bounds
            if (
                0 <= canvas_x < self.canvas.pixels_across
                and 0 <= canvas_y < self.canvas.pixels_tall
            ):
                pixel_num = canvas_y * self.canvas.pixels_across + canvas_x
                if pixel_num < len(self.canvas.pixels):
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
                        f'Canvas pixel sampled - Red: {red}, Green: {green}, Blue: {blue}, Alpha:'
                        f' {alpha}'
                    )

                    # Update all sliders with the sampled RGBA values
                    trigger = events.HashableEvent(0, name='R', value=red)
                    self.on_slider_event(event=event, trigger=trigger)

                    trigger = events.HashableEvent(0, name='G', value=green)
                    self.on_slider_event(event=event, trigger=trigger)

                    trigger = events.HashableEvent(0, name='B', value=blue)
                    self.on_slider_event(event=event, trigger=trigger)

                    trigger = events.HashableEvent(0, name='A', value=alpha)
                    self.on_slider_event(event=event, trigger=trigger)
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
                f'Screen pixel sampled - Red: {red}, Green: {green}, Blue: {blue}, Alpha: {alpha}'
                f' (default)'
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

    def _detect_clicked_slider(self, mouse_pos: tuple[int, int]) -> str | None:
        """Detect which slider text box was clicked.

        Args:
            mouse_pos: The mouse position (x, y)

        Returns:
            The name of the clicked slider ("red", "green", "blue") or None.

        """
        slider_names = ['red', 'green', 'blue']
        for name in slider_names:
            slider_attr = f'{name}_slider'
            if (
                hasattr(self, slider_attr)
                and hasattr(getattr(self, slider_attr), 'text_sprite')
                and getattr(self, slider_attr).text_sprite.rect.collidepoint(mouse_pos)
            ):
                return name
        return None

    def _commit_and_deactivate_slider(
        self, slider: SliderSprite, clicked_slider: str | None, slider_name: str
    ) -> None:
        """Commit the slider text value and deactivate the text sprite.

        Commits the current text input on a slider's text sprite, parsing as hex or
        decimal as appropriate, then deactivates the text sprite.

        Args:
            slider: The slider object with text_sprite attribute
            clicked_slider: Name of the slider that was clicked, or None
            slider_name: Name of this slider ("red", "green", "blue")

        """
        if not (
            hasattr(slider, 'text_sprite')
            and slider.text_sprite.active
            and (clicked_slider != slider_name or clicked_slider is None)
        ):
            return

        # Commit any uncommitted value before deactivating
        if not slider.text_sprite.text.strip():
            # If empty, restore original value
            slider.text_sprite.text = str(slider.original_value)
        else:
            # Try to commit the current text value - parse as hex if contains letters, otherwise
            # decimal
            try:
                text = slider.text_sprite.text.strip().lower()
                # Parse as hex if contains hex letters, otherwise decimal
                new_value = int(text, 16) if any(c in 'abcdef' for c in text) else int(text)

                if 0 <= new_value <= MAX_COLOR_CHANNEL_VALUE:
                    slider.value = new_value
                    # Update original value for future validations
                    slider.original_value = new_value
                    # Convert text to appropriate format based on selected tab
                    LOG.debug(f'DEBUG: Current slider_input_format: {self.slider_input_format}')
                    if self.slider_input_format == '%X':
                        slider.text_sprite.text = f'{new_value:02X}'
                        LOG.debug(
                            f'DEBUG: Converting {new_value} to hex: {slider.text_sprite.text}'
                        )
                    else:
                        slider.text_sprite.text = str(new_value)
                        LOG.debug(
                            f'DEBUG: Converting {new_value} to decimal: {slider.text_sprite.text}'
                        )
                    slider.text_sprite.update_text(slider.text_sprite.text)
                    slider.text_sprite.dirty = 2  # Force redraw
                else:
                    # Invalid range, restore original
                    slider.text_sprite.text = str(slider.original_value)
            except ValueError:
                # Invalid input, restore original
                slider.text_sprite.text = str(slider.original_value)

        slider.text_sprite.active = False
        slider.text_sprite.update_text(slider.text_sprite.text)

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
        for sprite in sprites:
            if hasattr(sprite, 'direction') and hasattr(sprite, 'visible') and sprite.visible:
                LOG.debug(
                    f'Scroll arrow clicked: direction={sprite.direction}, visible={sprite.visible}'
                )
                if sprite.direction == 'up':
                    # Clicked on up arrow - navigate to previous animation and scroll if needed
                    LOG.debug('Navigating to previous animation')
                    if hasattr(self, 'canvas') and self.canvas:
                        self.canvas.previous_animation()
                        # Scroll to show the current animation if needed
                        self.film_strip_coordinator.scroll_to_current_animation()
                        # Update film strips to reflect the animation change
                        self.film_strip_coordinator.update_film_strips_for_animated_sprite_update()
                    return

        # Check if click is on any slider text box and deactivate others
        clicked_slider = self._detect_clicked_slider(event.pos)

        # Deactivate all slider text boxes except the one clicked (if any)
        # Also commit values when clicking outside of any slider text box
        for slider_name in ('red', 'green', 'blue'):
            slider_attr = f'{slider_name}_slider'
            if hasattr(self, slider_attr):
                self._commit_and_deactivate_slider(
                    getattr(self, slider_attr), clicked_slider, slider_name
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
                f' offset={self.film_strip_scroll_offset}'
            )

    def on_tab_change_event(self, tab_format: str) -> None:
        """Handle tab control format change.

        Args:
            tab_format (str): The selected format ("%d" or "%H")

        """
        self.log.info(f'Tab control changed to format: {tab_format}')

        # Store the current format for slider text input
        self.slider_input_format = tab_format

        # Update slider text display format if they have values
        self._update_slider_text_format(tab_format)

    def _update_slider_text_format(self, tab_format: str | None = None) -> None:
        """Update slider text display format.

        Args:
            tab_format (str): The format to use ("%X" for hex, "%d" for decimal).
                             If None, uses the current slider_input_format.

        """
        if tab_format is None:
            tab_format = getattr(self, 'slider_input_format', '%d')

        if hasattr(self, 'red_slider') and hasattr(self.red_slider, 'text_sprite'):
            if tab_format == '%X':
                # Convert to hex
                self.red_slider.text_sprite.text = f'{self.red_slider.value:02X}'
            else:
                # Convert to decimal
                self.red_slider.text_sprite.text = str(self.red_slider.value)
            self.red_slider.text_sprite.update_text(self.red_slider.text_sprite.text)

        if hasattr(self, 'green_slider') and hasattr(self.green_slider, 'text_sprite'):
            if tab_format == '%X':
                # Convert to hex
                self.green_slider.text_sprite.text = f'{self.green_slider.value:02X}'
            else:
                # Convert to decimal
                self.green_slider.text_sprite.text = str(self.green_slider.value)
            self.green_slider.text_sprite.update_text(self.green_slider.text_sprite.text)

        if hasattr(self, 'blue_slider') and hasattr(self.blue_slider, 'text_sprite'):
            if tab_format == '%X':
                # Convert to hex
                self.blue_slider.text_sprite.text = f'{self.blue_slider.value:02X}'
            else:
                # Convert to decimal
                self.blue_slider.text_sprite.text = str(self.blue_slider.value)
            self.blue_slider.text_sprite.update_text(self.blue_slider.text_sprite.text)

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
    def on_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:  # type: ignore[override]
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
    def on_mouse_motion_event(self: Self, event: events.HashableEvent) -> None:  # type: ignore[override]
        """Handle mouse motion events.

        Args:
            event (pygame.event.Event): The event to handle

        """
        # Handle slider hover effects
        self._update_slider_hover_effects(event.pos)

        for sprite in self.all_sprites:
            if hasattr(sprite, 'on_mouse_motion_event'):
                sprite.on_mouse_motion_event(event)

    def _is_slider_hovered(self, slider_name: str, mouse_pos: tuple[int, int]) -> bool:
        """Check if the mouse is hovering over a slider.

        Args:
            slider_name: The slider attribute name (e.g., "alpha_slider")
            mouse_pos: The current mouse position (x, y)

        Returns:
            True if the mouse is hovering over the slider.

        """
        return hasattr(self, slider_name) and getattr(self, slider_name).rect.collidepoint(
            mouse_pos
        )

    def _is_slider_text_hovered(self, slider_name: str, mouse_pos: tuple[int, int]) -> bool:
        """Check if the mouse is hovering over a slider's text sprite.

        Uses absolute coordinates for text sprites.

        Args:
            slider_name: The slider attribute name (e.g., "alpha_slider")
            mouse_pos: The current mouse position (x, y)

        Returns:
            True if the mouse is hovering over the slider's text sprite.

        """
        if not hasattr(self, slider_name):
            return False
        slider = getattr(self, slider_name)
        return hasattr(slider, 'text_sprite') and slider.text_sprite.rect.collidepoint(mouse_pos)

    def _draw_alpha_slider_gradient_border(self, bbox: BitmappySprite) -> None:
        """Draw a gradient border on the alpha slider bounding box.

        The gradient goes from right (opaque) to left (transparent).

        Args:
            bbox: The alpha slider bounding box sprite

        """
        bbox.image.fill((0, 0, 0, 0))  # Clear surface

        # Draw individual pixels to create gradient effect
        width = bbox.rect.width
        height = bbox.rect.height

        # Draw border pixels with fixed gradient from right (255) to left (0)
        for x in range(int(width)):
            # Calculate opacity based on position: right side = 255, left side = 0
            pixel_alpha = int((255 * x) / width) if width > 0 else 0
            pixel_color = (pixel_alpha, 0, pixel_alpha, pixel_alpha)  # RGBA

            # Draw top and bottom border lines
            if x < width - 1:  # Don't draw the last pixel to avoid overlap
                bbox.image.set_at((x, 0), pixel_color)  # Top border
                bbox.image.set_at((x, height - 1), pixel_color)  # Bottom border

        # Draw left and right border lines
        for y in range(int(height)):
            # Left border (transparent)
            bbox.image.set_at((0, y), (0, 0, 0, 0))  # Transparent
            # Right border (opaque magenta)
            right_color = (255, 0, 255, 255)
            bbox.image.set_at((width - 1, y), right_color)

        bbox.visible = True
        bbox.dirty = 1

    def _update_slider_bbox_hover(
        self, bbox_attr: str, *, is_hovered: bool, border_color: tuple[int, int, int]
    ) -> None:
        """Update a slider bounding box border based on hover state.

        Args:
            bbox_attr: The bounding box attribute name (e.g., "red_slider_bbox")
            is_hovered: Whether the mouse is currently hovering over the slider
            border_color: The RGB color for the border

        """
        if not hasattr(self, bbox_attr):
            return

        bbox = getattr(self, bbox_attr)
        if is_hovered and not bbox.visible:
            bbox.image.fill((0, 0, 0, 0))  # Clear surface
            pygame.draw.rect(
                bbox.image,
                border_color,
                (0, 0, bbox.rect.width, bbox.rect.height),
                2,
            )
            bbox.visible = True
            bbox.dirty = 1
        elif not is_hovered and bbox.visible:
            bbox.image.fill((0, 0, 0, 0))  # Clear surface
            bbox.visible = False
            bbox.dirty = 1

    def _update_slider_text_hover_border(self, slider_name: str, *, is_text_hovered: bool) -> None:
        """Update a slider text sprite's white hover border.

        Args:
            slider_name: The slider attribute name (e.g., "red_slider")
            is_text_hovered: Whether the mouse is hovering over the text sprite

        """
        if not (hasattr(self, slider_name) and hasattr(getattr(self, slider_name), 'text_sprite')):
            return

        text_sprite = getattr(self, slider_name).text_sprite
        if is_text_hovered:
            # Add white border to text sprite
            if not hasattr(text_sprite, 'hover_border_added'):
                # Create a white border by drawing on the text sprite's image
                pygame.draw.rect(
                    text_sprite.image,
                    (255, 255, 255),
                    (0, 0, text_sprite.rect.width, text_sprite.rect.height),
                    2,
                )
                text_sprite.hover_border_added = True
                text_sprite.dirty = 1
        # Remove white border
        elif hasattr(text_sprite, 'hover_border_added') and text_sprite.hover_border_added:
            # Force text sprite to redraw without border
            text_sprite.update_text(text_sprite.text)
            text_sprite.hover_border_added = False
            text_sprite.dirty = 1

    def _update_slider_hover_effects(self, mouse_pos: tuple[int, int]) -> None:
        """Update slider hover effects based on mouse position.

        Args:
            mouse_pos: The current mouse position (x, y)

        """
        # Check if mouse is hovering over any slider
        alpha_hover = self._is_slider_hovered('alpha_slider', mouse_pos)
        red_hover = self._is_slider_hovered('red_slider', mouse_pos)
        green_hover = self._is_slider_hovered('green_slider', mouse_pos)
        blue_hover = self._is_slider_hovered('blue_slider', mouse_pos)

        # Update alpha slider border (uses gradient, not solid border)
        if hasattr(self, 'alpha_slider_bbox') and self.alpha_slider_bbox is not None:
            if alpha_hover and not self.alpha_slider_bbox.visible:
                self._draw_alpha_slider_gradient_border(self.alpha_slider_bbox)
            elif not alpha_hover and self.alpha_slider_bbox.visible:
                # Hide alpha border
                self.alpha_slider_bbox.image.fill((0, 0, 0, 0))  # Clear surface
                self.alpha_slider_bbox.visible = False
                self.alpha_slider_bbox.dirty = 1

        # Update colored slider borders
        self._update_slider_bbox_hover(
            'red_slider_bbox', is_hovered=red_hover, border_color=(255, 0, 0)
        )
        self._update_slider_bbox_hover(
            'green_slider_bbox', is_hovered=green_hover, border_color=(0, 255, 0)
        )
        self._update_slider_bbox_hover(
            'blue_slider_bbox', is_hovered=blue_hover, border_color=(0, 0, 255)
        )

        # Update text box hover effects (white borders)
        # Check if mouse is hovering over any slider text boxes (use absolute coordinates)
        slider_names = ['alpha_slider', 'red_slider', 'green_slider', 'blue_slider']
        for slider_name in slider_names:
            text_hovered = self._is_slider_text_hovered(slider_name, mouse_pos)
            self._update_slider_text_hover_border(slider_name, is_text_hovered=text_hovered)

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
            (self.canvas.pixels_across, self.canvas.pixels_tall), pygame.SRCALPHA
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
            f'Committed panned pixels and image to frame {current_animation}[{current_frame}]'
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
            'Updated film strip animated sprite frame'
            f' {current_animation}[{current_frame}] with pixels and image'
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
        self.log.debug(f'Updated film strip for frame {current_animation}[{current_frame}]')

        # Keep the panning state active so user can continue panning
        # Don't clear _original_frame_pixels, pan_offset_x, pan_offset_y, or _panning_active
        # The viewport will continue to show the panned view

        self.log.debug('Panned buffer committed, panning state preserved for continued panning')

    def _handle_slider_text_input(self, event: events.HashableEvent) -> bool | None:
        """Handle text input for active slider text boxes.

        Args:
            event: The key down event.

        Returns:
            True if escape was pressed (consume event), None if handled but not escape,
            or False if no slider text box was active.

        """
        sliders = ['red_slider', 'green_slider', 'blue_slider', 'alpha_slider']
        for slider_name in sliders:
            slider = getattr(self, slider_name, None)
            if slider is not None and hasattr(slider, 'text_sprite') and slider.text_sprite.active:
                slider.text_sprite.on_key_down_event(event)
                # If escape was pressed, consume the event to prevent game quit
                if event.key == pygame.K_ESCAPE:
                    return True
                return None
        return False

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

    def _handle_ctrl_key_shortcuts(self, event: events.HashableEvent, mod: int) -> bool:
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
                    f'Ctrl+Shift+{direction} arrow pressed - panning {direction.lower()}'
                )
                self._handle_canvas_panning(delta_x, delta_y)
                return True

        return False

    def _is_any_controller_in_slider_mode(self) -> bool:
        """Check if any controller is currently in slider mode.

        Returns:
            True if at least one controller is in a slider mode.

        """
        if not hasattr(self, 'mode_switcher'):
            return False

        for controller_id in self.mode_switcher.controller_modes:
            controller_mode = self.mode_switcher.get_controller_mode(controller_id)
            if controller_mode and controller_mode.value in {
                'r_slider',
                'g_slider',
                'b_slider',
            }:
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
            return None

        # Check if any slider text box is active and handle text input
        slider_result = self._handle_slider_text_input(event)
        if slider_result is not False:
            return slider_result  # type: ignore[return-value]

        # Check if any film strip is in text editing mode and handle text input
        film_strip_result = self._handle_film_strip_text_input(event)
        if film_strip_result is not False:
            return film_strip_result  # type: ignore[return-value]

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
            return None

        # Handle undo/redo and Ctrl-based keyboard shortcuts
        # Get modifier keys from HashableEvent (which wraps pygame events)
        mod = getattr(event, 'mod', 0)
        if self._handle_ctrl_key_shortcuts(event, mod):
            return None

        # Handle slider mode navigation with arrow keys
        if self._is_any_controller_in_slider_mode():
            if event.key == pygame.K_UP:
                self.log.debug('UP arrow pressed - navigating to previous slider mode')
                self.controller_handler.handle_slider_mode_navigation('up')
                return None
            if event.key == pygame.K_DOWN:
                self.log.debug('DOWN arrow pressed - navigating to next slider mode')
                self.controller_handler.handle_slider_mode_navigation('down')
            return None

        # Handle animation navigation and film strip scrolling (UP/DOWN arrows)
        if self._handle_arrow_key_navigation(event):
            return None

        # Route to canvas or parent (only if not in slider mode)
        if not self._is_any_controller_in_slider_mode():
            self._route_to_canvas_or_parent(event)

        return None

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
                        f'Frame-specific undo successful for {current_animation}[{current_frame}]'
                    )
                    # Force canvas redraw to show the undone changes
                    if hasattr(self, 'canvas') and self.canvas:
                        self.canvas.force_redraw()
                    return
                self.log.warning(
                    f'Frame-specific undo failed for {current_animation}[{current_frame}]'
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
            f'Canvas state before sync: animation={current_animation}, frame={current_frame}'
        )
        self.log.debug(f'Available animations: {list(animations.keys())}')

        # Check if current animation still exists
        if current_animation not in animations:
            self.log.warning(
                f"Current animation '{current_animation}' no longer exists, switching to first"
                f' available'
            )
            if animations:
                # Switch to the first available animation
                first_animation = next(iter(animations.keys()))
                self.canvas.show_frame(first_animation, 0)
                self.log.info(f"Switched to animation '{first_animation}', frame 0")
                return
            self.log.error('No animations available - this should not happen')
            return

        # Check if current frame index is valid
        frames = animations[current_animation]
        if current_frame is None or current_frame < 0 or current_frame >= len(frames):
            self.log.warning(
                f"Current frame {current_frame} is invalid for animation '{current_animation}' with"
                f' {len(frames)} frames'
            )
            # Switch to the last valid frame
            valid_frame = max(0, len(frames) - 1)
            self.canvas.show_frame(current_animation, valid_frame)
            self.log.info(f"Switched to frame {valid_frame} of animation '{current_animation}'")
            return

        # If we get here, the canvas state is valid
        self.log.debug(
            f"Canvas state is valid: animation='{current_animation}', frame={current_frame}"
        )

        # Force a complete canvas refresh to ensure everything is in sync
        self.canvas.force_redraw()

        # Update film strips to reflect the current state
        if hasattr(self, 'update_film_strips_for_frame'):
            self.film_strip_coordinator.update_film_strips_for_frame(
                current_animation, current_frame
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
                        f'Frame-specific redo successful for {current_animation}[{current_frame}]'
                    )
                    # Force canvas redraw to show the redone changes
                    if hasattr(self, 'canvas') and self.canvas:
                        self.canvas.force_redraw()
                    return
                self.log.warning(
                    f'Frame-specific redo failed for {current_animation}[{current_frame}]'
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
            self.log.warning(f"Animation '{animation}' not found for copying")
            return

        frames = self.canvas.animated_sprite._animations[animation]  # type: ignore[reportPrivateUsage]
        if frame >= len(frames):
            self.log.warning(f"Frame {frame} not found in animation '{animation}'")
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

        self.log.debug(f"Copied frame {frame} from animation '{animation}' to clipboard")

    def _handle_paste_frame(self) -> None:
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
            self.log.warning(f"Animation '{animation}' not found for pasting")
            return

        frames = self.canvas.animated_sprite._animations[animation]  # type: ignore[reportPrivateUsage]
        if frame >= len(frames):
            self.log.warning(f"Frame {frame} not found in animation '{animation}'")
            return

        target_frame = frames[frame]

        # Check if dimensions match
        clipboard_width = self._frame_clipboard['width']
        clipboard_height = self._frame_clipboard['height']
        target_width, target_height = target_frame.get_size()

        if clipboard_width != target_width or clipboard_height != target_height:
            self.log.warning(
                'Cannot paste frame: dimension mismatch (clipboard:'
                f' {clipboard_width}x{clipboard_height}, target: {target_width}x{target_height})'
            )
            return

        # Create undo/redo operation for the paste
        from glitchygames.bitmappy.history.undo_redo import OperationType

        # Store original frame data for undo
        original_pixels = target_frame.get_pixel_data()
        original_duration = target_frame.duration

        # Apply the paste operation
        self._apply_frame_paste_for_undo_redo(
            animation, frame, self._frame_clipboard['pixels'], self._frame_clipboard['duration']
        )

        # Add to undo stack
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.FRAME_PASTE,
            description=(
                f'Paste frame from'
                f' {self._frame_clipboard["animation"]}[{self._frame_clipboard["frame"]}] to'
                f' {animation}[{frame}]'
            ),
            undo_data={
                'animation': animation,
                'frame': frame,
                'pixels': original_pixels,
                'duration': original_duration,
            },
            redo_data={
                'animation': animation,
                'frame': frame,
                'pixels': self._frame_clipboard['pixels'],
                'duration': self._frame_clipboard['duration'],
            },
        )

        # Update canvas display
        if hasattr(self.canvas, 'force_redraw'):
            self.canvas.force_redraw()

        self.log.debug(f'Pasted frame from clipboard to {animation}[{frame}]')

    def _apply_frame_paste_for_undo_redo(
        self, animation: str, frame: int, pixels: list[tuple[int, ...]], duration: float
    ) -> bool:
        """Apply frame paste for undo/redo operations.

        Args:
            animation: Name of the animation
            frame: Frame index
            pixels: Pixel data to apply
            duration: Frame duration

        Returns:
            True if successful, False otherwise

        """
        try:
            if (
                not hasattr(self, 'canvas')
                or not self.canvas
                or not hasattr(self.canvas, 'animated_sprite')
            ):
                self.log.warning('Canvas or animated sprite not available for frame paste')
                return False

            # Get the target frame
            if animation not in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                self.log.warning(f"Animation '{animation}' not found for frame paste")
                return False

            frames = self.canvas.animated_sprite._animations[animation]  # type: ignore[reportPrivateUsage]
            if frame >= len(frames):
                self.log.warning(f"Frame {frame} not found in animation '{animation}'")
                return False

            target_frame = frames[frame]

            # Apply the pixel data and duration
            target_frame.set_pixel_data(pixels)
            target_frame.duration = duration

            # Update the canvas pixels if this is the currently displayed frame
            if (
                hasattr(self, 'selected_animation')
                and hasattr(self, 'selected_frame')
                and self.selected_animation == animation
                and self.selected_frame == frame
                and hasattr(self.canvas, 'pixels')
            ):
                self.canvas.pixels = pixels.copy()
                if hasattr(self.canvas, 'dirty_pixels'):
                    self.canvas.dirty_pixels = [True] * len(pixels)
                if hasattr(self.canvas, 'dirty'):
                    self.canvas.dirty = 1

            self.log.debug(f'Applied frame paste to {animation}[{frame}]')
            return True

        except AttributeError, IndexError, KeyError, TypeError, ValueError:
            self.log.exception('Error applying frame paste')
            return False

    def _apply_pixel_change_for_undo_redo(
        self, x: int, y: int, color: tuple[int, int, int]
    ) -> None:
        """Apply a pixel change for undo/redo operations.

        Args:
            x: X coordinate of the pixel
            y: Y coordinate of the pixel
            color: Color to set the pixel to

        """
        if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'canvas_interface'):
            # Set flag to prevent undo tracking during undo/redo operations
            self._applying_undo_redo = True
            try:
                # Use the canvas interface to set the pixel
                self.canvas.canvas_interface.set_pixel_at(x, y, color)
                self.log.debug(f'Applied undo/redo pixel change at ({x}, {y}) to color {color}')
            finally:
                # Always reset the flag
                self._applying_undo_redo = False
        else:
            self.log.warning('Canvas or canvas interface not available for undo/redo')

    def _apply_frame_selection_for_undo_redo(self, animation: str, frame: int) -> bool:
        """Apply a frame selection for undo/redo operations.

        Args:
            animation: Name of the animation to select
            frame: Frame index to select

        Returns:
            True if the frame selection was applied successfully, False otherwise

        """
        try:
            if hasattr(self, 'canvas') and self.canvas:
                # Set flag to prevent undo tracking during undo/redo operations
                self._applying_undo_redo = True
                try:
                    # Switch to the specified frame
                    self.canvas.show_frame(animation, frame)
                    self.log.debug(f'Applied undo/redo frame selection: {animation}[{frame}]')
                    return True
                finally:
                    # Always reset the flag
                    self._applying_undo_redo = False
            else:
                self.log.warning('Canvas not available for frame selection undo/redo')
                return False
        except AttributeError, IndexError, KeyError, TypeError, ValueError:
            self.log.exception('Error applying frame selection undo/redo')
            return False

    def _add_frame_for_undo_redo(
        self, frame_index: int, animation_name: str, frame_data: dict[str, Any]
    ) -> bool:
        """Add a frame for undo/redo operations.

        Args:
            frame_index: Index where the frame should be added
            animation_name: Name of the animation
            frame_data: Data about the frame to add

        Returns:
            True if the frame was added successfully, False otherwise

        """
        import pygame

        from glitchygames.sprites.animated import SpriteFrame

        try:
            if (
                not hasattr(self, 'canvas')
                or not self.canvas
                or not hasattr(self.canvas, 'animated_sprite')
            ):
                self.log.warning('Canvas or animated sprite not available for frame addition')
                return False

            # Create a new frame from the frame data
            # Create surface from frame data
            surface = pygame.Surface((frame_data['width'], frame_data['height']))
            if frame_data.get('pixels'):
                # Convert pixel data to surface
                pixel_array = pygame.PixelArray(surface)
                for i, pixel in enumerate(frame_data['pixels']):
                    if i < len(pixel_array.flat):  # type: ignore[union-attr]
                        pixel_array.flat[i] = pixel  # type: ignore[union-attr]
                del pixel_array  # Release the pixel array

            # Create the frame object
            new_frame = SpriteFrame(surface=surface, duration=frame_data.get('duration', 1.0))

            # Add the frame to the animation
            self.canvas.animated_sprite.add_frame(animation_name, new_frame, frame_index)

            # Update the canvas's selected frame index if necessary
            if self.canvas.animated_sprite.frame_manager.current_animation == animation_name:
                # If we're adding a frame at or before the current position, increment the frame
                # index
                if self.canvas.animated_sprite.frame_manager.current_frame >= frame_index:
                    self.canvas.animated_sprite.frame_manager.current_frame += 1

                # Ensure the frame index is within bounds
                max_frame = len(self.canvas.animated_sprite._animations[animation_name]) - 1  # type: ignore[reportPrivateUsage]
                if self.canvas.animated_sprite.frame_manager.current_frame > max_frame:
                    self.canvas.animated_sprite.frame_manager.current_frame = max(0, max_frame)

                # Update the canvas to show the correct frame
                self.canvas.show_frame(
                    animation_name, self.canvas.animated_sprite.frame_manager.current_frame
                )

            self.film_strip_coordinator.refresh_all_film_strip_widgets(animation_name)

            # Notify the scene about the frame insertion for proper UI updates
            self.film_strip_coordinator.on_frame_inserted(animation_name, frame_index)

            self.log.debug(
                f"Added frame {frame_index} to animation '{animation_name}' for undo/redo"
            )
            return True

        except AttributeError, IndexError, KeyError, TypeError, ValueError, pygame.error:
            self.log.exception('Error adding frame for undo/redo')
            return False

    def _stop_animation_and_adjust_frame_before_deletion(
        self, animation_name: str, frame_index: int
    ) -> None:
        """Stop animation playback and adjust the frame index before frame deletion.

        Args:
            animation_name: Name of the animation being modified.
            frame_index: Index of the frame about to be deleted.

        """
        if not (
            hasattr(self.canvas.animated_sprite, 'frame_manager')
            and self.canvas.animated_sprite.frame_manager.current_animation == animation_name
        ):
            return

        self.canvas.animated_sprite._is_playing = False  # type: ignore[reportPrivateUsage]

        # Adjust current frame index if necessary
        if self.canvas.animated_sprite.frame_manager.current_frame >= frame_index:
            if self.canvas.animated_sprite.frame_manager.current_frame > 0:
                self.canvas.animated_sprite.frame_manager.current_frame -= 1
            else:
                self.canvas.animated_sprite.frame_manager.current_frame = 0

    def _adjust_canvas_frame_after_deletion(self, animation_name: str, frame_index: int) -> None:
        """Adjust canvas frame selection after a frame has been deleted.

        Args:
            animation_name: Name of the animation that was modified.
            frame_index: Index of the frame that was deleted.

        """
        if self.canvas.animated_sprite.frame_manager.current_animation != animation_name:
            return

        # Adjust the canvas's current frame index to select the previous frame
        if self.canvas.animated_sprite.frame_manager.current_frame >= frame_index:
            if self.canvas.animated_sprite.frame_manager.current_frame > 0:
                # Select the previous frame
                self.canvas.animated_sprite.frame_manager.current_frame -= 1
                self.log.debug(
                    'Selected previous frame'
                    f' {self.canvas.animated_sprite.frame_manager.current_frame}'
                    ' after frame deletion'
                )
            else:
                # If we were at frame 0 and removed it, stay at frame 0 (which is
                # now the next frame)
                self.canvas.animated_sprite.frame_manager.current_frame = 0
                self.log.debug('Stayed at frame 0 after deleting frame 0')

        # Ensure the frame index is within bounds
        max_frame = len(self.canvas.animated_sprite._animations[animation_name]) - 1  # type: ignore[reportPrivateUsage]
        if self.canvas.animated_sprite.frame_manager.current_frame > max_frame:
            self.canvas.animated_sprite.frame_manager.current_frame = max(0, max_frame)

        # Update the canvas to show the correct frame
        self.canvas.show_frame(
            animation_name, self.canvas.animated_sprite.frame_manager.current_frame
        )

    def _delete_frame_for_undo_redo(self, frame_index: int, animation_name: str) -> bool:
        """Delete a frame for undo/redo operations.

        Args:
            frame_index: Index of the frame to delete
            animation_name: Name of the animation

        Returns:
            True if the frame was deleted successfully, False otherwise

        """
        try:
            if (
                not hasattr(self, 'canvas')
                or not self.canvas
                or not hasattr(self.canvas, 'animated_sprite')
            ):
                self.log.warning('Canvas or animated sprite not available for frame deletion')
                return False

            if animation_name not in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                self.log.warning(f"Animation '{animation_name}' not found")
                return False

            frames = self.canvas.animated_sprite._animations[animation_name]  # type: ignore[reportPrivateUsage]
            if not (0 <= frame_index < len(frames)):
                self.log.warning(
                    f"Frame index {frame_index} out of range for animation '{animation_name}'"
                )
                return False

            # Stop animation to prevent race conditions during frame deletion
            self._stop_animation_and_adjust_frame_before_deletion(animation_name, frame_index)

            frames.pop(frame_index)

            # Update the canvas's selected frame index if necessary and select the previous frame
            self._adjust_canvas_frame_after_deletion(animation_name, frame_index)

            self.film_strip_coordinator.refresh_all_film_strip_widgets(animation_name)

            # Notify the scene about the frame removal for proper UI updates
            self.film_strip_coordinator.on_frame_removed(animation_name, frame_index)

            self.log.debug(
                f"Deleted frame {frame_index} from animation '{animation_name}' for undo/redo"
            )
            return True

        except AttributeError, IndexError, KeyError, TypeError, ValueError:
            self.log.exception('Error deleting frame for undo/redo')
            return False

    def _reorder_frame_for_undo_redo(
        self, old_index: int, new_index: int, animation_name: str
    ) -> bool:
        """Reorder frames for undo/redo operations.

        Args:
            old_index: Original index of the frame
            new_index: New index of the frame
            animation_name: Name of the animation

        Returns:
            True if the frame was reordered successfully, False otherwise

        """
        try:
            if (
                not hasattr(self, 'canvas')
                or not self.canvas
                or not hasattr(self.canvas, 'animated_sprite')
            ):
                self.log.warning('Canvas or animated sprite not available for frame reordering')
                return False

            # Reorder frames in the animation
            if animation_name in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                frames = self.canvas.animated_sprite._animations[animation_name]  # type: ignore[reportPrivateUsage]
                if 0 <= old_index < len(frames) and 0 <= new_index < len(frames):
                    # Move the frame from old_index to new_index
                    frame = frames.pop(old_index)
                    frames.insert(new_index, frame)

                    # Update the film strip if it exists
                    if hasattr(self, 'film_strip_widget') and self.film_strip_widget:
                        self.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
                        self.film_strip_widget.update_layout()
                        self.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
                        self.film_strip_widget.mark_dirty()

                    self.log.debug(
                        f'Reordered frame from {old_index} to {new_index} in animation'
                        f" '{animation_name}' for undo/redo"
                    )
                    return True
                self.log.warning(f"Frame indices out of range for animation '{animation_name}'")
                return False
            self.log.warning(f"Animation '{animation_name}' not found")
            return False

        except AttributeError, IndexError, KeyError, TypeError:
            self.log.exception('Error reordering frame for undo/redo')
            return False

    def _add_animation_for_undo_redo(
        self, animation_name: str, animation_data: dict[str, Any]
    ) -> bool:
        """Add an animation for undo/redo operations.

        Args:
            animation_name: Name of the animation to add
            animation_data: Data about the animation to add

        Returns:
            True if the animation was added successfully, False otherwise

        """
        import pygame

        from glitchygames.sprites.animated import SpriteFrame

        try:
            if (
                not hasattr(self, 'canvas')
                or not self.canvas
                or not hasattr(self.canvas, 'animated_sprite')
            ):
                self.log.warning('Canvas or animated sprite not available for animation addition')
                return False

            # Create the animation with its frames
            for frame_data in animation_data.get('frames', []):
                # Create surface from frame data
                surface = pygame.Surface((frame_data['width'], frame_data['height']))
                if frame_data.get('pixels'):
                    # Convert pixel data to surface
                    pixel_array = pygame.PixelArray(surface)
                    for i, pixel in enumerate(frame_data['pixels']):
                        if i < len(pixel_array.flat):  # type: ignore[union-attr]
                            pixel_array.flat[i] = pixel  # type: ignore[union-attr]
                    del pixel_array  # Release the pixel array

                # Create the frame object
                new_frame = SpriteFrame(surface=surface, duration=frame_data.get('duration', 1.0))

                # Add the frame to the animation
                self.canvas.animated_sprite._animations[animation_name] = (  # type: ignore[reportPrivateUsage]
                    self.canvas.animated_sprite._animations.get(animation_name, [])  # type: ignore[reportPrivateUsage]
                )
                self.canvas.animated_sprite._animations[animation_name].append(new_frame)  # type: ignore[reportPrivateUsage]

            # Update the film strip if it exists
            if hasattr(self, 'film_strip_widget') and self.film_strip_widget:
                self.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
                self.film_strip_widget.update_layout()
                self.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
                self.film_strip_widget.mark_dirty()

            # Force update of all film strip widgets
            if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:
                for film_strip_sprite in self.film_strip_sprites.values():
                    if (
                        hasattr(film_strip_sprite, 'film_strip_widget')
                        and film_strip_sprite.film_strip_widget
                    ):
                        # Completely refresh the film strip widget to ensure it shows current data
                        film_strip_sprite.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
                        film_strip_sprite.film_strip_widget._calculate_layout()  # type: ignore[reportPrivateUsage]
                        film_strip_sprite.film_strip_widget.update_layout()
                        film_strip_sprite.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
                        film_strip_sprite.film_strip_widget.mark_dirty()
                        film_strip_sprite.dirty = 1

            self.log.debug(f"Added animation '{animation_name}' for undo/redo")
            return True

        except AttributeError, IndexError, KeyError, TypeError, ValueError, pygame.error:
            self.log.exception('Error adding animation for undo/redo')
            return False

    def _delete_animation_for_undo_redo(self, animation_name: str) -> bool:
        """Delete an animation for undo/redo operations.

        Args:
            animation_name: Name of the animation to delete

        Returns:
            True if the animation was deleted successfully, False otherwise

        """
        try:
            if (
                not hasattr(self, 'canvas')
                or not self.canvas
                or not hasattr(self.canvas, 'animated_sprite')
            ):
                self.log.warning('Canvas or animated sprite not available for animation deletion')
                return False

            # Remove the animation
            if animation_name in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                del self.canvas.animated_sprite._animations[animation_name]  # type: ignore[reportPrivateUsage]

                # Update the film strip if it exists
                if hasattr(self, 'film_strip_widget') and self.film_strip_widget:
                    self.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
                    self.film_strip_widget.update_layout()
                    self.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
                    self.film_strip_widget.mark_dirty()

                # Force update of all film strip widgets
                if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:
                    for film_strip_sprite in self.film_strip_sprites.values():
                        if (
                            hasattr(film_strip_sprite, 'film_strip_widget')
                            and film_strip_sprite.film_strip_widget
                        ):
                            # Completely refresh the film strip widget to ensure it shows current
                            # data
                            film_strip_sprite.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
                            film_strip_sprite.film_strip_widget._calculate_layout()  # type: ignore[reportPrivateUsage]
                            film_strip_sprite.film_strip_widget.update_layout()
                            film_strip_sprite.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
                            film_strip_sprite.film_strip_widget.mark_dirty()
                            film_strip_sprite.dirty = 1

                # CRITICAL: Recreate film strips to reflect the deleted animation
                self.film_strip_coordinator.on_sprite_loaded(self.canvas.animated_sprite)

                self.log.debug(f"Deleted animation '{animation_name}' for undo/redo")
                return True
            self.log.warning(f"Animation '{animation_name}' not found")
            return False

        except AttributeError, KeyError, TypeError:
            self.log.exception('Error deleting animation for undo/redo')
            return False

    def _apply_controller_position_for_undo_redo(
        self, controller_id: int, position: tuple[int, int], mode: str | None = None
    ) -> bool:
        """Apply a controller position change for undo/redo operations.

        Args:
            controller_id: ID of the controller
            position: New position (x, y)
            mode: Controller mode (optional)

        Returns:
            True if the position was applied successfully, False otherwise

        """
        try:
            # Set flag to prevent undo tracking during undo/redo operations
            self._applying_undo_redo = True
            try:
                # Update controller position in mode switcher
                if hasattr(self, 'mode_switcher') and self.mode_switcher:
                    self.mode_switcher.save_controller_position(controller_id, position)

                    # Update visual indicator
                    if hasattr(self, 'controller_handler'):
                        self.controller_handler.update_controller_canvas_visual_indicator(
                            controller_id
                        )

                    self.log.debug(
                        f'Applied undo/redo controller position: {controller_id} -> {position}'
                    )
                    return True
                self.log.warning('Mode switcher not available for controller position undo/redo')
                return False
            finally:
                # Always reset the flag
                self._applying_undo_redo = False
        except AttributeError, KeyError, TypeError:
            self.log.exception('Error applying controller position undo/redo')
            return False

    def _apply_controller_mode_for_undo_redo(self, controller_id: int, mode: str) -> bool:
        """Apply a controller mode change for undo/redo operations.

        Args:
            controller_id: ID of the controller
            mode: New controller mode

        Returns:
            True if the mode was applied successfully, False otherwise

        """
        try:
            # Set flag to prevent undo tracking during undo/redo operations
            self._applying_undo_redo = True
            try:
                # Update controller mode in mode switcher
                if hasattr(self, 'mode_switcher') and self.mode_switcher:
                    from glitchygames.bitmappy.controllers.modes import ControllerMode

                    # Convert string to ControllerMode enum
                    try:
                        controller_mode = ControllerMode(mode)
                    except ValueError:
                        self.log.warning(f'Invalid controller mode: {mode}')
                        return False

                    # Switch to the new mode
                    import time

                    current_time = time.time()
                    self.mode_switcher.controller_modes[controller_id].switch_to_mode(
                        controller_mode, current_time
                    )

                    # Update visual indicator
                    if hasattr(self, 'controller_handler'):
                        self.controller_handler.update_controller_visual_indicator_for_mode(
                            controller_id, controller_mode
                        )

                    self.log.debug(f'Applied undo/redo controller mode: {controller_id} -> {mode}')
                    return True
                self.log.warning('Mode switcher not available for controller mode undo/redo')
                return False
            finally:
                # Always reset the flag
                self._applying_undo_redo = False
        except AttributeError, KeyError, TypeError, ValueError:
            self.log.exception('Error applying controller mode undo/redo')
            return False

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
                    pixel_changes_list,  # type: ignore[arg-type]
                )
                self.log.debug(
                    f'Submitted {pixel_count} pixel changes for frame'
                    f' {current_animation}[{current_frame}] undo/redo tracking'
                )
            else:
                # Fall back to global tracking
                self.canvas_operation_tracker.add_pixel_changes(pixel_changes_list)  # type: ignore[arg-type]
                self.log.debug(
                    f'Submitted {pixel_count} pixel changes for global undo/redo tracking'
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
            '-v', '--version', action='store_true', help='print the game version and exit'
        )
        parser.add_argument('-s', '--size', default='32x32')

    @override
    def _handle_scene_key_events(self, event: events.HashableEvent) -> None:
        """Handle scene-level key events."""
        self.log.debug(f'Scene-level key event: {event.key}')

        # Call our custom keyboard handler
        self.on_key_down_event(event)

    @override
    def on_drop_file_event(self, event: events.HashableEvent) -> None:  # type: ignore[override]
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

        super().handle_event(event)  # type: ignore[arg-type]

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
                self.log.debug(f'First RGB triplet: {first_triplet}')
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
        self, film_strip_widget: FilmStripWidget, animation: str, frame: int
    ) -> None:
        """Delegate to FilmStripCoordinator."""
        self.film_strip_coordinator.on_film_strip_frame_selected(
            film_strip_widget, animation, frame
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
        """Get the current color from the color picker.

        Returns:
            tuple: The current color.

        """
        # Get color from sliders if available
        if (
            hasattr(self, 'red_slider')
            and hasattr(self, 'green_slider')
            and hasattr(self, 'blue_slider')
        ):
            try:
                red = int(self.red_slider.value)
                green = int(self.green_slider.value)
                blue = int(self.blue_slider.value)
                self.log.debug(
                    f'DEBUG: _get_current_color() returning color from sliders: ({red}, {green},'
                    f' {blue})'
                )
                return (red, green, blue)
            except (ValueError, AttributeError) as e:
                self.log.debug(f'DEBUG: _get_current_color() error getting slider values: {e}')

        # Default to white if sliders not available
        self.log.debug('DEBUG: _get_current_color() sliders not available, returning white')
        return (255, 255, 255)

    def update_color_well_from_sliders(self) -> None:
        """Update the color well with current slider values."""
        self.log.debug('DEBUG: _update_color_well_from_sliders called')
        if hasattr(self, 'color_well') and self.color_well:
            # Get current slider values
            red_value = self.red_slider.value if hasattr(self, 'red_slider') else 0
            green_value = self.green_slider.value if hasattr(self, 'green_slider') else 0
            blue_value = self.blue_slider.value if hasattr(self, 'blue_slider') else 0
            alpha_value = self.alpha_slider.value if hasattr(self, 'alpha_slider') else 0

            self.log.debug(
                f'DEBUG: Slider values - R:{red_value}, G:{green_value}, B:{blue_value},'
                f' A:{alpha_value}'
            )
            self.log.debug(f'DEBUG: Color well before update: {self.color_well.active_color}')

            # Update color well
            self.color_well.active_color = (red_value, green_value, blue_value, alpha_value)

            # Force color well to redraw
            if hasattr(self.color_well, 'dirty'):
                self.color_well.dirty = 1

            # Also dirty the main scene to ensure redraw
            self.dirty = 1

            # Force color well to update its display
            if hasattr(self.color_well, 'force_redraw'):
                self.color_well.force_redraw()  # type: ignore[union-attr]

            self.log.debug(
                f'DEBUG: Updated color well to ({red_value}, {green_value}, {blue_value})'
            )
        else:
            self.log.debug('DEBUG: No color_well found or color_well is None')

    # ──────────────────────────────────────────────────────────────────────
    # Controller event delegation (methods extracted to controller_handler.py)
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
    def on_joy_hat_motion_event(self, event: events.HashableEvent) -> None:  # type: ignore[override]
        """Handle joystick hat motion events by delegating to ControllerEventHandler."""
        self.controller_handler.on_joy_hat_motion_event(event)

    @override
    def on_joy_axis_motion_event(self, event: events.HashableEvent) -> None:  # type: ignore[override]
        """Handle joystick axis motion events by delegating to ControllerEventHandler."""
        self.controller_handler.on_joy_axis_motion_event(event)

    @override
    def on_joy_ball_motion_event(self, event: events.HashableEvent) -> None:  # type: ignore[override]
        """Handle joystick ball motion events by delegating to ControllerEventHandler."""
        self.controller_handler.on_joy_ball_motion_event(event)

    @override
    def on_controller_axis_motion_event(self, event: events.HashableEvent) -> None:  # type: ignore[override]
        """Handle controller axis motion events by delegating to ControllerEventHandler."""
        self.controller_handler.on_controller_axis_motion_event(event)


def main() -> None:
    """Run the main function.

    Raises:
        None

    """
    LOG.setLevel(logging.INFO)

    # Set up signal handling to prevent multiprocessing issues on macOS
    def signal_handler(signum: int) -> None:
        """Handle shutdown signals gracefully."""
        LOG.info(f'Received signal {signum}, shutting down gracefully...')
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # type: ignore[arg-type]
    signal.signal(signal.SIGTERM, signal_handler)  # type: ignore[arg-type]

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
