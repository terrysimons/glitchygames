#!/usr/bin/env python3
"""Glitchy Games Bitmap Editor."""

# ruff: noqa: FBT001 FBT002
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Self

if TYPE_CHECKING:
    import argparse

import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals
from glitchygames import events
from glitchygames.engine import GameEngine
from glitchygames.events.mouse import MousePointer
from glitchygames.pixels import image_from_pixels, pixels_from_data
from glitchygames.scenes import Scene
from glitchygames.sprites import BitmappySprite
from glitchygames.ui import ColorWellSprite, InputDialog, MenuBar, MenuItem, SliderSprite

LOG = logging.getLogger('game')

# Turn on sprite debugging
BitmappySprite.DEBUG = True
MAX_PIXELS_ACROSS = 64
MIN_PIXELS_ACROSS = 1
MAX_PIXELS_TALL = 64
MIN_PIXELS_TALL = 1
MIN_COLOR_VALUE = 0
MAX_COLOR_VALUE = 255


class GGUnhandledMenuItemError(Exception):
    """Glitchy Games Unhandled Menu Item Error."""


class InputConfirmationDialogScene(Scene):
    """Input Confirmation Dialog Scene."""

    log = LOG
    NAME = 'InputConfirmationDialog'
    DIALOG_TEXT = 'Would you like to do a thing?'
    CONFIRMATION_TEXT = 'Confirm'
    CANCEL_TEXT = 'Cancel'
    VERSION = ''

    def __init__(
        self: Self,
        previous_scene: Scene,
        options: dict | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
        """Initialize the Input Confirmation Dialog Scene.

        Args:
            previous_scene (Scene): The previous scene.
            options (dict, optional): Options for the scene. Defaults to None.
            groups (pygame.sprite.LayeredDirty, optional): Sprite groups.
                   Defaults to pygame.sprite.LayeredDirty().

        Returns:
            None

        Raises:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(options=options, groups=groups)
        self.previous_scene = previous_scene

        self.dialog = InputDialog(
            name=self.NAME,
            dialog_text=self.DIALOG_TEXT,
            confirm_text=self.CONFIRMATION_TEXT,
            x=self.screen.get_rect().center[0] // 2,
            y=self.screen.get_rect().center[1] // 2,
            width=self.screen_width // 2,
            height=self.screen_height // 2,
            parent=self,
            groups=self.all_sprites,
        )

    def setup(self: Self) -> None:
        """Setup the scene.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """
        self.dialog.cancel_button.callbacks = {
            'on_left_mouse_button_up_event': self.on_cancel_event
        }
        self.dialog.confirm_button.callbacks = {
            'on_left_mouse_button_up_event': self.on_confirm_event
        }

        self.dialog.add(self.all_sprites)

    def cleanup(self: Self) -> None:
        """Cleanup the scene.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """
        self.next_scene = self

    def dismiss(self: Self) -> None:
        """Dismiss the dialog.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """
        self.previous_scene.next_scene = self.previous_scene
        self.next_scene = self.previous_scene

    def on_cancel_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the cancel event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None
        """
        self.log.info(f'Cancel: event: {event}, trigger: {trigger}')
        self.dismiss()

    def on_confirm_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the confirm event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None
        """
        self.log.info(f'{type(self)}on_confirm_event: event: {event}, trigger: {trigger}')
        self.dismiss()

    def on_input_box_submit_event(self: Self, control: object) -> None:
        """Handle the input box submit event.

        Args:
            control (object): The control object.

        Returns:
            None

        Raises:
            None
        """
        self.log.info(f'{self.name} Got text input from: {control.name}: {control.text}')

    def on_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the mouse button up event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None
        """
        self.dialog.input_box.activate()

    def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the key up event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None
        """
        if self.dialog.input_box.active:
            self.dialog.on_key_up_event(event)
        elif event.key == pygame.K_TAB:
            self.dialog.input_box.activate()
        else:
            super().on_key_up_event(event)

    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the key down event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None
        """
        if self.dialog.input_box.active:
            self.dialog.on_key_down_event(event)
        else:
            super().on_key_up_event(event)


class NewCanvasDialogScene(InputConfirmationDialogScene):
    """New Canvas Dialog Scene."""

    log = LOG
    NAME = 'New Canvas'
    DIALOG_TEXT = 'Are you sure you want to clear the canvas?'
    CONFIRMATION_TEXT = 'Clear'
    CANCEL_TEXT = 'Cancel'

    def __init__(
        self: Self,
        previous_scene: Scene,
        options: dict | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
        """Initialize the New Canvas Dialog Scene.

        Args:
            previous_scene (Scene): The previous scene.
            options (dict, optional): Options for the scene. Defaults to None.
            groups (pygame.sprite.LayeredDirty, optional): Sprite groups.
                   Defaults to pygame.sprite.LayeredDirty().

        Returns:
            None

        Raises:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(previous_scene, options=options, groups=pygame.sprite.LayeredDirty())

    def on_confirm_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the confirm event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None
        """
        self.log.info(f'New Canvas: event: {event}, trigger: {trigger}')
        self.previous_scene.canvas.on_load_file_event(self.dialog.input_box, self.dialog.input_box)
        self.dismiss()


class LoadDialogScene(InputConfirmationDialogScene):
    """Load Dialog Scene."""

    log = LOG
    NAME = 'Load Sprite'
    DIALOG_TEXT = 'Would you like to load a sprite?'
    CONFIRMATION_TEXT = 'Load'
    CANCEL_TEXT = 'Cancel'
    VERSION = ''

    def __init__(
        self: Self,
        previous_scene: Scene,
        options: dict | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
        """Initialize the Load Dialog Scene.

        Args:
            previous_scene (Scene): The previous scene.
            options (dict, optional): Options for the scene. Defaults to None.
            groups (pygame.sprite.LayeredDirty, optional): Sprite groups.
                   Defaults to pygame.sprite.LayeredDirty().

        Returns:
            None

        Raises:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(previous_scene, options=options, groups=pygame.sprite.LayeredDirty())

    def on_confirm_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the confirm event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None
        """
        self.log.info(f'Load File: event: {event}, trigger: {trigger}')
        self.previous_scene.canvas.on_load_file_event(self.dialog.input_box, self.dialog.input_box)
        self.dismiss()


class SaveDialogScene(InputConfirmationDialogScene):
    """Save Dialog Scene."""

    log = LOG
    NAME = 'Save Sprite'
    DIALOG_TEXT = 'Would you like to save your sprite?'
    CONFIRMATION_TEXT = 'Save'
    CANCEL_TEXT = 'Cancel'
    VERSION = ''

    def __init__(
        self: Self,
        previous_scene: Scene,
        options: dict | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
        """Initialize the Save Dialog Scene.

        Args:
            previous_scene (Scene): The previous scene.
            options (dict, optional): Options for the scene. Defaults to None.
            groups (pygame.sprite.LayeredDirty, optional): Sprite groups.
                   Defaults to pygame.sprite.LayeredDirty().

        Returns:
            None

        Raises:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(previous_scene, options=options, groups=pygame.sprite.LayeredDirty())

    def on_confirm_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the confirm event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None
        """
        self.log.info(f'Save File: event: {event}, trigger: {trigger}')
        self.previous_scene.canvas.on_save_file_event(self.dialog.input_box, self.dialog.input_box)
        self.dismiss()


class BitmapPixelSprite(BitmappySprite):
    """Bitmap Pixel Sprite."""

    log = LOG
    PIXEL_CACHE: ClassVar = {}

    def __init__(
        self: Self,
        x: int = 0,
        y: int = 0,
        width: int = 1,
        height: int = 1,
        name: str | None = None,
        pixel_number: int = 0,
        border_thickness: int = 1,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
        """Initialize the Bitmap Pixel Sprite."""
        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)

        self.pixel_number = pixel_number
        self.pixel_width = width
        self.pixel_height = height
        self.border_thickness = border_thickness
        self.color = (96, 96, 96)
        self.pixel_color = (0, 0, 0)
        self.x = x
        self.y = y

        self.rect = pygame.draw.rect(
            self.image, self.color, (self.x, self.y, self.width, self.height), self.border_thickness
        )

    @property
    def pixel_color(self: Self) -> tuple[int, int, int]:
        """Get the pixel color.

        Args:
            None

        Returns:
            tuple[int, int, int]: The pixel color.

        Raises:
            None
        """
        return self._pixel_color

    @pixel_color.setter
    def pixel_color(self: Self, new_pixel_color: tuple[int, int, int]) -> None:
        """Set the pixel color.

        Args:
            new_pixel_color (tuple): The new pixel color.

        Returns:
            None

        Raises:
            None
        """
        self._pixel_color = new_pixel_color
        self.dirty = 1

    def update(self: Self) -> None:
        """Update the sprite.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """
        cache_key = (self.pixel_color, self.border_thickness)
        cached_image = BitmapPixelSprite.PIXEL_CACHE.get(cache_key)

        if not cached_image:
            self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.image.fill((0,0,0,0))  # Start with transparent

            # Draw main pixel
            pygame.draw.rect(
                self.image, self.pixel_color, (0, 0, self.width, self.height)
            )

            # Draw border if needed
            if self.border_thickness:
                pygame.draw.rect(
                    self.image, self.color, (0, 0, self.width, self.height), self.border_thickness
                )

            # Convert surface for better performance
            self.image = self.image.convert_alpha()
            BitmapPixelSprite.PIXEL_CACHE[cache_key] = self.image
        else:
            self.image = cached_image  # No need to copy since we converted the surface

        self.rect = self.image.get_rect(x=self.rect.x, y=self.rect.y)

    def on_pixel_update_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the pixel update event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None
        """
        if self.callbacks:
            callback = self.callbacks.get('on_pixel_update_event', None)

            if callback:
                callback(event=event, trigger=self)

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the left mouse button down event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None
        """
        self.dirty = 1
        self.on_pixel_update_event(event)

    # def on_left_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
    #     # There's not a good way to pass any useful info, so for now, pass None
    #     # since we're not using the event for anything in this class.
    #     self.on_left_mouse_button_down_event(None)


class Canvas(BitmappySprite):
    """Canvas."""

    def __init__(self: Self) -> None:
        """Create a Canvas."""

    def update(self: Self) -> None:
        """Update the canvas."""
        # Draw the miniview pixel canvas
        # Draw the pixel canvas
        # Draw the pixel canvas border
        # Draw the pixel canvas grid


class CanvasSprite(BitmappySprite):
    """Canvas Sprite."""

    log = LOG

    def __init__(
        self,
        name='Canvas',
        x=0,
        y=0,
        pixels_across=32,
        pixels_tall=32,
        pixel_width=16,
        pixel_height=16,
        groups=None,
    ):
        """Initialize the Canvas Sprite."""
        # Calculate dimensions first
        width = pixels_across * pixel_width
        height = pixels_tall * pixel_height

        # Initialize parent class first to create rect
        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            groups=groups,
        )

        # Store pixel-related attributes
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall
        self.pixel_width = pixel_width
        self.pixel_height = pixel_height

        # Initialize pixels with magenta as the transparent/background color
        self.pixels = [(255, 0, 255) for _ in range(pixels_across * pixels_tall)]
        self.dirty_pixels = [True] * len(self.pixels)
        self.background_color = (128, 128, 128)
        self.active_color = (0, 0, 0)
        self.border_thickness = 1

        # Create initial surface
        self.image = pygame.Surface((width, height))
        self.rect = self.image.get_rect(x=x, y=y)

        # Get screen dimensions from pygame
        screen_info = pygame.display.Info()
        screen_width = screen_info.current_w

        # Create miniview - position in top right corner
        self.mini_view = MiniView(
            pixels=self.pixels,
            x=screen_width - (pixels_across * 2) - 10,
            y=32,
            width=pixels_across,
            height=pixels_tall,
            groups=groups
        )

        # Add MiniView to the sprite groups explicitly
        if groups:
            if isinstance(groups, (list, tuple)):
                for group in groups:
                    group.add(self.mini_view)
            else:
                groups.add(self.mini_view)

        # Force initial draw
        self.dirty = 1
        self.force_redraw()

    def update(self):
        """Update the canvas display."""
        # Check if mouse is outside canvas
        mouse_pos = pygame.mouse.get_pos()

        # Get window size
        screen_info = pygame.display.Info()
        screen_rect = pygame.Rect(0, 0, screen_info.current_w, screen_info.current_h)

        # If mouse is outside window or canvas, clear cursor
        if not screen_rect.collidepoint(mouse_pos) or not self.rect.collidepoint(mouse_pos):
            if hasattr(self, 'mini_view'):
                self.log.info("Mouse outside canvas/window, clearing miniview cursor")
                self.mini_view.clear_cursor()

        if self.dirty:
            self.force_redraw()
            self.dirty = 0

    def force_redraw(self):
        """Force a complete redraw of the canvas."""
        self.image.fill(self.background_color)

        # Draw all pixels, regardless of dirty state
        for i, pixel in enumerate(self.pixels):
            x = (i % self.pixels_across) * self.pixel_width
            y = (i // self.pixels_across) * self.pixel_height
            pygame.draw.rect(
                self.image,
                pixel,
                (x, y, self.pixel_width, self.pixel_height)
            )
            pygame.draw.rect(
                self.image,
                (64, 64, 64),
                (x, y, self.pixel_width, self.pixel_height),
                self.border_thickness
            )
            self.dirty_pixels[i] = False

        self.log.debug(f"Canvas force redraw complete with {len(self.pixels)} pixels")

    def on_left_mouse_button_down_event(self, event):
        """Handle the left mouse button down event."""
        if self.rect.collidepoint(event.pos):
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height
            pixel_num = y * self.pixels_across + x

            self.pixels[pixel_num] = self.active_color
            self.dirty_pixels[pixel_num] = True
            self.dirty = 1

            # Update miniview
            if hasattr(self, 'mini_view'):
                self.mini_view.on_pixel_update_event(event, self)

    def on_left_mouse_drag_event(self, event, trigger):
        """Handle mouse drag events."""
        # For drag events, we treat them the same as button down
        self.on_left_mouse_button_down_event(event)

    def on_mouse_motion_event(self, event):
        """Handle mouse motion events."""
        if self.rect.collidepoint(event.pos):
            # Convert mouse position to pixel coordinates
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height

            # Check if the coordinates are within valid range
            if (0 <= x < self.pixels_across and 0 <= y < self.pixels_tall):
                if hasattr(self, 'mini_view'):
                    self.mini_view.update_canvas_cursor(x, y, self.active_color)
            else:
                if hasattr(self, 'mini_view'):
                    self.mini_view.clear_cursor()
        else:
            if hasattr(self, 'mini_view'):
                self.mini_view.clear_cursor()

    def on_pixel_update_event(self, event, trigger):
        """Handle pixel update events."""
        if hasattr(trigger, 'pixel_number'):
            pixel_num = trigger.pixel_number
            new_color = trigger.pixel_color
            self.log.info(f"Canvas updating pixel {pixel_num} to color {new_color}")

            self.pixels[pixel_num] = new_color
            self.dirty_pixels[pixel_num] = True
            self.dirty = 1

            # Update miniview
            self.mini_view.on_pixel_update_event(event, trigger)

    def on_mouse_leave_window_event(self, event):
        """Handle mouse leaving window event."""
        self.log.info("Mouse left window, clearing miniview cursor")
        if hasattr(self, 'mini_view'):
            self.mini_view.clear_cursor()

    def on_mouse_enter_sprite_event(self, event):
        """Handle mouse entering canvas."""
        self.log.info("Mouse entered canvas")
        if hasattr(self, 'mini_view'):
            # Update cursor position immediately
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height
            if 0 <= x < self.pixels_across and 0 <= y < self.pixels_tall:
                self.mini_view.update_canvas_cursor(x, y, self.active_color)

    def on_mouse_exit_sprite_event(self, event):
        """Handle mouse exiting canvas."""
        self.log.info("Mouse exited canvas")
        if hasattr(self, 'mini_view'):
            self.mini_view.clear_cursor()


class MiniView(BitmappySprite):
    """Mini View."""

    log = LOG
    BACKGROUND_COLORS = [
        (0, 255, 255),    # Cyan
        (0, 0, 0),        # Black
        (128, 128, 128),  # Gray
        (255, 255, 255),  # White
        (255, 0, 255),    # Magenta
        (0, 255, 0),      # Green
        (0, 0, 255),      # Blue
        (255, 255, 0),    # Yellow
        (64, 64, 64),     # Dark Gray
        (192, 192, 192),  # Light Gray
    ]

    def __init__(self, pixels, x, y, width, height, name='Mini View', groups=None):
        self.pixels_across = width
        self.pixels_tall = height
        pixel_width, pixel_height = self.pixels_per_pixel(width, height)
        actual_width = width * pixel_width
        actual_height = height * pixel_height

        super().__init__(
            x=x,
            y=y,
            width=actual_width,
            height=actual_height,
            name=name,
            groups=groups
        )

        self.pixels = pixels
        self.dirty_pixels = [True] * len(pixels)
        self.background_color_index = 0
        self.background_color = self.BACKGROUND_COLORS[self.background_color_index]

        # Create initial surface
        self.image = pygame.Surface((actual_width, actual_height))
        self.rect = self.image.get_rect(x=x, y=y)

        # Initialize cursor and mouse tracking state
        self.canvas_cursor_pos = None
        self.cursor_color = (0, 0, 0)  # Will be updated from canvas's active color
        self.mouse_in_canvas = False

        self.dirty = 1
        self.force_redraw()
        self.log.info("MiniView initialized")

    def on_left_mouse_button_down_event(self, event):
        """Handle left mouse button to cycle background color."""
        if self.rect.collidepoint(event.pos):
            self.log.info(f"MiniView clicked at {event.pos}, rect is {self.rect}")
            old_color = self.background_color
            self.background_color_index = (self.background_color_index + 1) % len(self.BACKGROUND_COLORS)
            self.background_color = self.BACKGROUND_COLORS[self.background_color_index]
            self.log.info(f"MiniView background color changing from {old_color} to {self.background_color}")
            self.dirty = 1
            self.log.info("Setting dirty flag and calling force_redraw")
            self.force_redraw()
            return True
        return False

    def update_canvas_cursor(self, x, y, active_color=None):
        """Update the cursor position and color from the main canvas."""
        if x is None or y is None:
            self.clear_cursor()
            return

        if not (0 <= x < self.pixels_across and 0 <= y < self.pixels_tall):
            self.clear_cursor()
            return

        if active_color is not None:
            self.cursor_color = active_color

        old_pos = self.canvas_cursor_pos
        self.canvas_cursor_pos = (x, y)

        if old_pos != self.canvas_cursor_pos:
            self.dirty = 1

    def on_pixel_update_event(self, event, trigger):
        """Handle pixel update events."""
        if hasattr(trigger, 'pixel_number'):
            pixel_num = trigger.pixel_number
            new_color = trigger.pixel_color
            self.log.info(f"MiniView updating pixel {pixel_num} to color {new_color}")

            self.pixels[pixel_num] = new_color
            self.dirty_pixels[pixel_num] = True
            self.dirty = 1

    def force_redraw(self):
        """Force a complete redraw of the miniview."""
        self.log.info(f"Starting force_redraw with background color {self.background_color}")
        self.image.fill(self.background_color)
        pixel_width, pixel_height = self.pixels_per_pixel(self.pixels_across, self.pixels_tall)

        # Draw all non-magenta pixels
        for i, pixel in enumerate(self.pixels):
            if pixel != (255, 0, 255):  # Skip magenta pixels
                x = (i % self.pixels_across) * pixel_width
                y = (i // self.pixels_across) * pixel_height
                pygame.draw.rect(
                    self.image,
                    pixel,
                    (x, y, pixel_width, pixel_height)
                )

        # # Only draw cursor if we have a valid position AND mouse is in canvas
        # canvas = None
        # for group in self.groups():
        #     for sprite in group.sprites():
        #         if isinstance(sprite, CanvasSprite):
        #             canvas = sprite
        #             break
        #     if canvas:
        #         break

        # if (self.canvas_cursor_pos is not None and
        #     canvas and
        #     canvas.rect.collidepoint(pygame.mouse.get_pos())):
        #     x = self.canvas_cursor_pos[0] * pixel_width
        #     y = self.canvas_cursor_pos[1] * pixel_height
        #     pygame.draw.rect(
        #         self.image,
        #         self.cursor_color,
        #         (x, y, pixel_width, pixel_height),
        #         1  # Border thickness
        #     )

        self.log.debug(f"MiniView force redraw complete with background {self.background_color}")

    def update(self):
        """Update the miniview display."""
        # Get mouse position and window size
        mouse_pos = pygame.mouse.get_pos()
        screen_info = pygame.display.Info()
        screen_rect = pygame.Rect(0, 0, screen_info.current_w, screen_info.current_h)

        # Clear cursor if mouse is outside window
        if not screen_rect.collidepoint(mouse_pos):
            self.clear_cursor()

        if self.dirty:
            self.force_redraw()
            self.dirty = 0

    def clear_cursor(self):
        """Clear the cursor and force a redraw."""
        if self.canvas_cursor_pos is not None:
            self.log.info("Clearing miniview cursor")
            self.canvas_cursor_pos = None
            self.dirty = 1
            self.force_redraw()

    @staticmethod
    def pixels_per_pixel(pixels_across: int, pixels_tall: int) -> tuple[int, int]:
        """Calculate the size of each pixel in the miniview."""
        return (2, 2)  # Fixed 2x2 pixels for mini view


class BitmapEditorScene(Scene):
    """Bitmap Editor Scene."""

    log = LOG

    # Set your game name/version here.
    NAME = 'Bitmappy'
    VERSION = '1.0'

    def __init__(self, options: dict, groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize the Bitmap Editor Scene.

        Args:
            options (dict): The options.
            groups (pygame.sprite.LayeredDirty, optional): Sprite groups.
                   Defaults to pygame.sprite.LayeredDirty().

        Returns:
            None

        Raises:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(options=options, groups=groups)

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
            groups=self.all_sprites
        )

        # Add the raspberry icon with its specific height
        icon_path = Path(__file__).parent.parent / 'assets' / 'raspberry.cfg'
        self.menu_icon = MenuItem(
            name=None,
            x=4,  # Added 4px offset from left
            y=icon_y,
            width=16,
            height=icon_height,  # Use icon-specific height
            filename=icon_path,
            groups=self.all_sprites
        )
        self.menu_bar.add_menu(self.menu_icon)

        # Add all menus with full height
        new_menu = MenuItem(
            name="New",
            x=24,  # Slightly adjusted from icon
            y=menu_item_y,
            width=48,  # Reduced width to better match text
            height=menu_item_height,
            groups=self.all_sprites
        )
        self.menu_bar.add_menu(new_menu)

        save_menu = MenuItem(
            name="Save",
            x=72,  # Position directly after File menu
            y=menu_item_y,
            width=48,
            height=menu_item_height,
            groups=self.all_sprites
        )
        self.menu_bar.add_menu(save_menu)

        load_menu = MenuItem(
            name="Load",
            x=120,  # Position directly after Save menu
            y=menu_item_y,
            width=48,
            height=menu_item_height,
            groups=self.all_sprites
        )
        self.menu_bar.add_menu(load_menu)

        quit_menu = MenuItem(
            name="Quit",
            x=168,  # Position directly after Load menu
            y=menu_item_y,
            width=48,
            height=menu_item_height,
            groups=self.all_sprites
        )
        self.menu_bar.add_menu(quit_menu)

        # Calculate available space (adjusted for taller menu bar)
        bottom_margin = 100  # Space needed for sliders and color well
        available_height = self.screen_height - bottom_margin - menu_bar_height  # Use menu_bar_height instead of 32

        # Calculate pixel size to fit the canvas in the available space
        width, height = options.get('size', '32x32').split('x')
        pixels_across = int(width)
        pixels_tall = int(height)

        pixel_size = min(
            available_height // pixels_tall,  # Height-based size
            (self.screen_width * 2 // 3) // pixels_across  # Width-based size (use 2/3 of screen width)
        )

        # Create the canvas with the calculated pixel dimensions
        self.canvas = CanvasSprite(
            name='Bitmap Canvas',
            x=0,
            y=menu_bar_height,  # Position canvas right below menu bar
            pixels_across=pixels_across,
            pixels_tall=pixels_tall,
            pixel_width=pixel_size,
            pixel_height=pixel_size,
            groups=self.all_sprites,
        )

        width, height = options.get('size').split('x')
        CanvasSprite.WIDTH = int(width)
        CanvasSprite.HEIGHT = int(height)

        # First create the sliders
        slider_height = 9
        slider_width = 256
        slider_x = 10
        label_width = 32  # Width of the text sprite
        label_padding = 10  # Padding between slider and label
        well_padding = 20  # Padding between labels and color well

        self.red_slider = SliderSprite(
            name='R',
            x=slider_x,
            y=self.screen_height - 70,
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        self.green_slider = SliderSprite(
            name='G',
            x=slider_x,
            y=self.screen_height - 50,
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        self.blue_slider = SliderSprite(
            name='B',
            x=slider_x,
            y=self.screen_height - 30,
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        # Create the color well to the right of the sliders AND their labels
        well_size = 64
        total_slider_width = slider_width + label_padding + label_width  # Full width including label

        self.color_well = ColorWellSprite(
            name='Color Well',
            x=slider_x + total_slider_width + well_padding,  # Position after sliders + labels + padding
            y=self.screen_height - 70,  # Align with top slider
            width=well_size,
            height=well_size,
            parent=self,
            groups=self.all_sprites,
        )

        self.red_slider.value = 0
        self.blue_slider.value = 0
        self.green_slider.value = 0

        self.color_well.active_color = (
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
        )

        self.canvas.active_color = self.color_well.active_color

        self.all_sprites.clear(self.screen, self.background)

        # TODO: Plumb this into the scene manager
        # self.register_game_event('save', self.on_save_event)
        # self.register_game_event('load', self.on_load_event)

        self.new_canvas_dialog_scene = NewCanvasDialogScene(
            options=self.options, previous_scene=self
        )
        self.load_dialog_scene = LoadDialogScene(options=self.options, previous_scene=self)
        self.save_dialog_scene = SaveDialogScene(options=self.options, previous_scene=self)

        # These are set up in the GameEngine class.
        self.log.info(f'Game Options: {options}')

    def on_menu_item_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the menu item event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

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
    def on_new_file_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the new file event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None
        """
        self.new_canvas_dialog_scene.all_sprites.clear(
            self.new_canvas_dialog_scene.screen, self.screenshot
        )
        self.canvas.on_new_file_event(event=event, trigger=event)
        self.dirty = 1

    def on_new_canvas_dialog_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the new canvas dialog event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None
        """
        self.new_canvas_dialog_scene.all_sprites.clear(
            self.new_canvas_dialog_scene.screen, self.screenshot
        )
        self.next_scene = self.new_canvas_dialog_scene
        self.dirty = 1

    def on_load_dialog_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the load dialog event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None
        """
        self.load_dialog_scene.all_sprites.clear(self.load_dialog_scene.screen, self.screenshot)
        self.next_scene = self.load_dialog_scene
        self.dirty = 1

    def on_save_dialog_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the save dialog event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None
        """
        self.save_dialog_scene.all_sprites.clear(self.save_dialog_scene.screen, self.screenshot)
        self.next_scene = self.save_dialog_scene
        self.dirty = 1

    def on_color_well_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the color well event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None
        """
        self.log.info('COLOR WELL EVENT')

    def on_slider_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the slider event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None
        """
        value = trigger.value

        self.log.debug(f'Slider: event: {event}, trigger: {trigger} value: {value}')

        if value < MIN_COLOR_VALUE:
            value = MIN_COLOR_VALUE
            trigger.value = MIN_COLOR_VALUE
        elif value > MAX_COLOR_VALUE:
            value = MAX_COLOR_VALUE
            trigger.value = MAX_COLOR_VALUE

        if trigger.name == 'R':
            self.red_slider.value = value
        elif trigger.name == 'G':
            self.green_slider.value = value
        elif trigger.name == 'B':
            self.blue_slider.value = value

        self.color_well.active_color = (
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
        )
        self.canvas.active_color = (
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
        )

    def on_right_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the right mouse button up event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None
        """
        # If we're on the edge of an outside pixel, ignore
        # the right click so we don't crash.
        try:
            red, green, blue, alpha = self.screen.get_at(event.pos)
            self.log.info(f'Red: {red}, Green: {green}, Blue: {blue}, Alpha: {alpha}')

            # TODO: Make this a proper type.
            trigger = pygame.event.Event(0, {'name': 'R', 'value': red})
            self.on_slider_event(event=event, trigger=trigger)

            trigger = pygame.event.Event(0, {'name': 'G', 'value': green})
            self.on_slider_event(event=event, trigger=trigger)

            trigger = pygame.event.Event(0, {'name': 'B', 'value': blue})
            self.on_slider_event(event=event, trigger=trigger)
        except IndexError:
            pass

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the left mouse button down event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None
        """
        sprites = self.sprites_at_position(pos=event.pos)

        for sprite in sprites:
            sprite.on_left_mouse_button_down_event(event)

    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the left mouse button up event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None
        """
        sprites = self.sprites_at_position(pos=event.pos)

        for sprite in sprites:
            sprite.on_left_mouse_button_up_event(event)

    def on_left_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the left mouse drag event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None
        """
        self.canvas.on_left_mouse_drag_event(event, trigger)

        try:
            sprites = self.sprites_at_position(pos=event.pos)

            for sprite in sprites:
                sprite.on_left_mouse_drag_event(event, trigger)
        except AttributeError:
            pass

    # def on_menu_item_event(self, event: pygame.event.Event) -> None:
    #     """Handle the menu item event.

    #     Args:
    #         event (pygame.event.Event): The pygame event.
    #         trigger (object): The trigger object.

    #     Returns:
    #         None
    #     """
    #     self.log.info(f'Scene got menu item event: {event}')

    def on_mouse_drag_event(self, event: pygame.event.Event, trigger: object) -> None:
        """Handle mouse drag events.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None
        """
        sprites = self.sprites_at_position(pos=event.pos)
        for sprite in sprites:
            if isinstance(sprite, MenuItem):
                # MenuItem expects just event
                sprite.on_mouse_drag_event(event)
            elif hasattr(sprite, 'on_mouse_drag_event'):
                # Other sprites expect both event and trigger
                sprite.on_mouse_drag_event(event, trigger)

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> None:
        """Add command line arguments.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            None

        Raises:
            None
        """
        parser.add_argument(
            '-v', '--version', action='store_true', help='print the game version and exit'
        )
        parser.add_argument('-s', '--size', default='32x32')

    def handle_event(self, event):
        """Handle pygame events."""
        super().handle_event(event)

        if event.type == pygame.WINDOWLEAVE:
            # Notify sprites that mouse left window
            for sprite in self.all_sprites:
                if hasattr(sprite, 'on_mouse_leave_window_event'):
                    sprite.on_mouse_leave_window_event(event)


def main() -> None:
    """Main function.

    Args:
        None

    Returns:
        None

    Raises:
        None
    """
    icon_path = Path(__file__).parent / 'resources' / 'bitmappy.png'

    GameEngine(
        game=BitmapEditorScene,
        icon=icon_path
    ).start()


if __name__ == '__main__':
    main()
