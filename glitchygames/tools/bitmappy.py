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
    WIDTH = 32
    HEIGHT = 32
    DEBUG = False
    PIXEL_CACHE: ClassVar = {}

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str,
        has_mini_view: bool = True,
        groups: None | pygame.sprite.LayeredDirty = None,
    ) -> None:
        """Initialize the Canvas Sprite.

        Args:
            x (int): The x coordinate.
            y (int): The y coordinate.
            width (int): The width.
            height (int): The height.
            name (str): The name.
            has_mini_view (bool, optional): Whether or not to have a mini view.
                                            Defaults to True.
            groups (None, optional): Sprite groups. Defaults to None.

        Returns:
            None

        Raises:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)

        self.character_sprite = False

        self.border_thickness = 0
        self.border_margin = 0
        self.pixels_across = CanvasSprite.WIDTH
        self.pixels_tall = CanvasSprite.HEIGHT
        self.pixels = [(255, 0, 255)] * self.pixels_across * self.pixels_tall
        self.grid_line_width = 0
        self.pixel_boxes = []
        self.pixel_width = 1
        self.pixel_height = 1
        self.mini_view = None
        self.resize_widget = None
        self.active_color = (255, 255, 255)

        self.log.info(f'Canvas: {self.rect.x}, {self.rect.y}')

        self.name = 'Bitmap Canvas'

        if self.pixels_across >= self.pixels_tall:
            self.pixel_width = self.width // self.pixels_across - self.border_thickness * 2
            self.pixel_height = self.width // self.pixels_across - self.border_thickness * 2
        else:
            self.pixel_width = self.height // self.pixels_tall - self.border_thickness * 2
            self.pixel_height = self.height // self.pixels_tall - self.border_thickness * 2
        self.log.info(f'Pixels Across: {self.pixels_across}')
        self.log.info(f'Pixels Tall: {self.pixels_tall}')
        self.log.info('')

        # Generate a cache of all bitmap pixel sprites.
        # color = (0, 0, 0)
        # for r in range(256):
        #     for g in range(256):
        #         for b in range(256):
        #             color = (r, g, b)
        #             CanvasSprite.PIXEL_CACHE[color] = pygame.Surface((self.pixel_width,
        #                                                                self.pixel_height))

        self.log.info(f'Pixel Width: {self.pixel_width}')
        self.log.info(f'Pixel Height: {self.pixel_height}')

        # Can we change this to groups?
        self.all_sprites = groups

        # Create all pixel boxes at once
        self.pixel_boxes = [
            BitmapPixelSprite(
                name=f'pixel {i}',
                pixel_number=i,
                x=self.border_margin + ((i % self.pixels_across) * self.pixel_width),
                y=self.border_margin + ((i // self.pixels_across) * self.pixel_height),
                height=self.pixel_width,
                width=self.pixel_height,
            )
            for i in range(self.pixels_across * self.pixels_tall)
        ]

        # Add all sprites to group at once
        self.all_sprites.add(self.pixel_boxes)

        for i in range(self.pixels_across * self.pixels_tall):
            self.pixel_boxes[i].pixel_color = self.pixels[i]
            self.pixel_boxes[i].add(self.all_sprites)

            # This allows us to update the mini map.
            self.pixel_boxes[i].callbacks = {'on_pixel_update_event': self.on_pixel_update_event}

            # This draws the map box.
            self.pixel_boxes[i].dirty = 1

        if has_mini_view:
            pixel_width, pixel_height = MiniView.pixels_per_pixel(
                self.pixels_across, self.pixels_tall
            )

            self.mini_view = MiniView(
                pixels=self.pixels,
                x=self.screen_width - (self.pixels_across * pixel_width),
                y=self.rect.y + self.pixels_tall,
                width=self.pixels_across,
                height=self.pixels_tall,
            )
            self.all_sprites.add(self.mini_view)
            self.mini_view.pixels = self.pixels
            self.mini_view.rect.x = self.screen_width - self.mini_view.width
            self.mini_view.rect.y = self.rect.y

        self.update_anyway = False

        # Force initial position update
        for pixel in self.pixel_boxes:
            pixel.dirty = 1
        self.update()

    def on_pixel_update_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the pixel update event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None
        """
        if self.mini_view:
            self.mini_view.pixels[trigger.pixel_number] = trigger.pixel_color
            self.mini_view.dirty_pixels[trigger.pixel_number] = True
            self.mini_view.on_pixel_update_event(event, trigger)
            self.mini_view.dirty = 1

        self.pixel_boxes[trigger.pixel_number].pixel_color = trigger.pixel_color

        # if self.pixel_boxes[trigger.pixel_number].dirty:
        #     self.pixel_boxes[trigger.pixel_number].update()

        self.dirty = 1

    def update_nested_sprites(self: Self) -> None:
        """Update the nested sprites.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """
        if self.mini_view:
            self.mini_view.dirty = self.dirty

    def update(self: Self) -> None:
        """Update the sprite.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """
        x = 0
        y = 0
        self.border_thickness = 0
        self.border_margin = 0
        for pixel_box in self.pixel_boxes:
            if pixel_box.dirty:
                pixel_x = x * pixel_box.pixel_width
                pixel_y = y * pixel_box.pixel_height

                adjusted_pixel_box_width = (
                    pixel_box.pixel_width if x == 0 else pixel_box.pixel_width - 1
                )
                adjusted_pixel_box_height = (
                    pixel_box.pixel_height if y == 0 else pixel_box.pixel_height - 1
                )

                pixel_x = (
                    self.border_margin
                    + self.border_thickness
                    + (x * adjusted_pixel_box_width)
                    + (x * pixel_box.border_thickness)
                )
                pixel_y = (
                    self.border_margin
                    + self.border_thickness
                    + (y * adjusted_pixel_box_height)
                    + (y * pixel_box.border_thickness)
                )

                pixel_box.rect.x = pixel_x + self.rect.x
                pixel_box.rect.y = pixel_y + self.rect.y
                self.image.blit(pixel_box.image, (pixel_box.x, pixel_box.y))

                if self.mini_view:
                    self.mini_view.dirty = 1

            if (x + 1) % self.pixels_across == 0:
                x = 0
                y += 1
            else:
                x += 1

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the left mouse button down event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None
        """
        # Check for a sprite collision against the mouse pointer.
        #
        # First, we need to create a pygame Sprite that represents the tip of the mouse.
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse, group=self.all_sprites, dokill=False
        )

        for sprite in collided_sprites:
            sprite.pixel_color = self.active_color
            sprite.dirty = 1

            if type(sprite) == BitmapPixelSprite:
                self.on_pixel_update_event(event=event, trigger=sprite)
            elif sprite is not self:
                sprite.on_left_mouse_button_down_event(event)

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
        self.on_left_mouse_button_down_event(event)

    def on_new_file_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the new file event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None
        """
        for i, pixel in enumerate([(255, 0, 255)] * self.pixels_across * self.pixels_tall):
            event = pygame.event.Event(
                events.GAMEEVENT,
                {'action': 'on_new_file_event', 'pixel_color': pixel, 'pixel_number': i},
            )

            # Create a pixel update event for the mini map.
            self.on_pixel_update_event(event=event, trigger=event)

        self.dirty = 1
        # self.update()

    def on_save_file_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the save file event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None
        """
        pixels = [pixel_box.pixel_color for pixel_box in self.pixel_boxes]

        # Generate a new bitmappy sprite and tell it to save.
        save_sprite = BitmappySprite(
            x=0, y=0, width=self.pixels_across, height=self.pixels_tall, name='Tiley McTile Face'
        )

        save_sprite.image = image_from_pixels(
            pixels=pixels, width=save_sprite.width, height=save_sprite.height
        )

        self.log.info(f'Saving file as: {event.text}')
        save_sprite.save(filename=event.text)

        self.dirty = 1

        # self.save(filename='screenshot.cfg')

    def on_load_file_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the load file event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None
        """
        self.log.info(f'Loading file: {event.text}')

        load_sprite = BitmappySprite(
            filename=event.text, x=0, y=0, width=self.pixels_across, height=self.pixels_tall
        )

        pixel_data = pygame.image.tostring(load_sprite.image, 'RGB')

        pixels = pixels_from_data(pixel_data=pixel_data)

        # self.log.info(pixels)

        # Update the canvas' pixels across and tall
        self.pixels_across = load_sprite.width
        self.pixels_tall = load_sprite.height

        # pixels = [pixel_box.pixel_color for pixel_box in self.pixel_boxes]
        # pixels = [(255, 255, 255)] * len(pixels)

        # print(pixels)

        for i, pixel in enumerate(pixels):
            trigger.pixel_number = i
            trigger.pixel_color = pixel

            event = pygame.event.Event(
                events.GAMEEVENT,
                {'action': 'on_load_file_event', 'pixel_color': pixel, 'pixel_number': i},
            )

            # Create a pixel update event for the mini map.
            self.on_pixel_update_event(event=event, trigger=event)

        # for pixel_box in self.pixel_boxes:
        #     pixel_box.dirty = 1
        #     pixel_box.update()

        self.dirty = 1
        # self.update()


class MiniView(BitmappySprite):
    """Mini View of the canvas."""

    log = LOG

    @staticmethod
    def pixels_per_pixel(pixels_across: int, pixels_tall: int) -> tuple[int, int]:
        """Get the pixels per pixel."""
        pixel_width = 0
        pixel_height = 0

        if pixels_across < MAX_PIXELS_ACROSS:
            pixel_width = (
                MAX_PIXELS_ACROSS // pixels_across if pixels_across > 0 else MIN_PIXELS_ACROSS
            )

        if pixels_tall < MAX_PIXELS_TALL:
            pixel_height = MAX_PIXELS_TALL // pixels_tall if pixels_tall > 0 else MIN_PIXELS_TALL

        return (pixel_width, pixel_height)

    def __init__(
        self: Self,
        pixels: list,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
        super().__init__(x=x, y=y, width=width, height=height, groups=groups)
        self.pixels = pixels
        self.dirty_pixels = [False] * len(self.pixels)
        self.pixel_width, self.pixel_height = self.pixels_per_pixel(width, height)

        self.width = width * self.pixel_width
        self.height = height * self.pixel_height

        self.image = pygame.Surface((self.width, self.height))
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y

        self.color_palette = [(0, 255, 0), (255, 0, 255), (255, 255, 0), (0, 0, 0)]
        self.palette_index = 0

        # Force initial render
        self.dirty_pixels = [True] * len(self.pixels)
        self.dirty = 1

    def update(self: Self) -> None:
        """Update the mini view display."""
        x = 0
        y = 0
        for i, pixel in enumerate(self.pixels):
            color = self.color_palette[self.palette_index] if pixel == (255, 0, 255) else pixel
            pygame.draw.rect(
                self.image,
                color,
                ((x, y), (self.pixel_width, self.pixel_height))
            )

            if (x + self.pixel_width) % (self.width) == 0:
                x = 0
                y += self.pixel_height
            else:
                x += self.pixel_width

    def on_pixel_update_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle pixel updates in the mini view."""
        self.dirty = 1

    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button up to cycle palette colors."""
        self.palette_index = (self.palette_index + 1) % len(self.color_palette)
        self.dirty = 1


class BitmapEditorScene(Scene):
    """Bitmap Editor Scene."""

    log = LOG

    # Set your game name/version here.
    NAME = 'Bitmappy'
    VERSION = '1.0'

    def __init__(
        self: Self, options: dict, groups: pygame.sprite.LayeredDirty | None = None
    ) -> None:
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

        width, height = options.get('size').split('x')
        CanvasSprite.WIDTH = int(width)
        CanvasSprite.HEIGHT = int(height)

        self.menu_bar = MenuBar(
            name='Menu Bar', x=0, y=0, width=self.screen_width, height=20, groups=self.all_sprites
        )

        self.menu_icon = MenuItem(
            name=None,
            filename=Path(__file__).parent / 'resources' / 'bitmappy.cfg',
            x=0,
            y=0,
            width=16,
            height=self.menu_bar.height,
        )
        # # When we load the sprite, we set a name.
        # self.menu_icon.name = None

        self.menu_bar.add_menu_item(menu_item=self.menu_icon, menu=None)

        # self.new_menu_item = MenuItem(
        #     name='New',
        #     x=self.menu_icon.rect.topright[0],
        #     y=self.menu_icon.rect.y,
        #     width=40,
        #     height=self.menu_bar.height,
        #     parent=self,
        #     groups=self.all_sprites
        # )
        # self.save_menu_item = MenuItem(
        #     name='Save',
        #     x=self.new_menu_item.rect.topright[0],
        #     y=self.new_menu_item.rect.y,
        #     width=40,
        #     height=self.menu_bar.height,
        #     parent=self,
        #     groups=self.all_sprites
        # )
        # self.load_menu_item = MenuItem(
        #     name='Load',
        #     x=self.save_menu_item.rect.midright[0],
        #     y=self.save_menu_item.rect.y,
        #     width=40,
        #     height=self.menu_bar.height,
        #     parent=self,
        #     groups=self.all_sprites
        # )
        # self.quit_menu_item = MenuItem(
        #     name='Quit',
        #     x=self.load_menu_item.rect.midright[0],
        #     y=self.load_menu_item.rect.y,
        #     width=40,
        #     height=self.menu_bar.height,
        #     parent=self,
        #     groups=self.all_sprites
        # )

        # self.file_menu = MenuItem(
        #     name='File',
        #     width=32,
        #     height=16,
        #     groups=self.all_sprites
        # )
        # self.save_menu_item = MenuItem(
        #     name='Save',
        #     width=40,
        #     height=16,
        #     groups=self.all_sprites
        # )
        # self.load_menu_item = MenuItem(
        #     name='Load',
        #     width=40,
        #     height=16,
        #     groups=self.all_sprites
        # )
        # self.spacer_menu_item = MenuItem(
        #     name='----',
        #     width=40,
        #     height=16,
        #     groups=self.all_sprites
        # )
        # self.quit_menu_item = MenuItem(
        #     name='Quit',
        #     width=40,
        #     height=16,
        #     groups=self.all_sprites
        # )

        # self.edit_menu = MenuItem(
        #     name='Edit',
        #     width=32,
        #     height=16,
        #     groups=self.all_sprites
        # )

        # Add the menu icon as a root level menu item.
        # self.menu_bar.add_menu_item(menu_item=self.menu_icon, menu=None)
        # self.menu_bar.add_menu_item(menu_item=self.file_menu, menu=None)
        # self.menu_bar.add_menu_item(menu_item=self.edit_menu, menu=None)

        # self.menu_bar.add_menu_item(menu_item=self.save_menu_item, menu=None)
        # self.menu_bar.add_menu_item(menu_item=self.load_menu_item, menu=None)
        # self.menu_bar.add_menu_item(menu_item=self.quit_menu_item, menu=None)
        # self.file_menu.add_menu_item(menu_item=self.save_menu_item, menu=None)
        # self.file_menu.add_menu_item(menu_item=self.load_menu_item, menu=None)
        # self.file_menu.add_menu_item(menu_item=self.spacer_menu_item, menu=None)
        # self.file_menu.add_menu_item(menu_item=self.quit_menu_item, menu=None)

        # We'll use the top left quartile of the screen to draw the canvas.
        # We want a square canvas, so we'll use the height as our input.
        # self.canvas = CanvasSprite(
        #     name='Bitmap Canvas',
        #     x=0, y=self.menu_bar.rect.bottom + 10,
        #     width=int(self.screen_height * 0.75),
        #     height=int(self.screen_height * 0.75),
        #     groups=self.all_sprites
        # )
        self.canvas = CanvasSprite(
            name='Bitmap Canvas',
            x=0,
            y=32,
            width=int(self.screen_height * 0.75),
            height=int(self.screen_height * 0.75),
            groups=self.all_sprites,
        )

        slider_height = 9

        self.red_slider = SliderSprite(
            name='R',
            x=10,
            y=self.screen_height - 70,
            width=256,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )
        self.red_slider.callbacks = {'on_left_mouse_button_down_event': self.on_slider_event}

        self.green_slider = SliderSprite(
            name='G',
            x=10,
            y=self.screen_height - 50,
            width=256,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )
        self.green_slider.callbacks = {'on_left_mouse_button_down_event': self.on_slider_event}

        self.blue_slider = SliderSprite(
            name='B',
            x=10,
            y=self.screen_height - 30,
            width=256,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )
        self.blue_slider.callbacks = {'on_left_mouse_button_down_event': self.on_slider_event}

        self.red_slider.value = 0
        self.blue_slider.value = 0
        self.green_slider.value = 0

        self.color_well = ColorWellSprite(
            name='Colorwell',
            x=self.red_slider.rect.midright[0] + 30,
            y=self.red_slider.rect.y,
            width=64,
            height=64,
            groups=groups,
        )

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
        elif event.menu_item.name == 'Load':
            self.on_load_dialog_event(event=event)
        elif event.menu.name == 'Quit':
            self.log.info('User quit from menu item.')
            self.scene_manager.quit()
        else:
            raise GGUnhandledMenuItemError(f'Unhandled Menu Item: {event}')
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
