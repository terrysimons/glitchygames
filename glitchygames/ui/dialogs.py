#!/usr/bin/env python3
"""Dialog scene classes for GlitchyGames UI.

This module contains dialog scene classes that provide input dialogs
for various operations like saving, loading, and creating new files.
"""

from __future__ import annotations

import logging
from typing import Self

import pygame
from glitchygames.scenes import Scene
from glitchygames.ui import InputDialog

LOG = logging.getLogger("game.ui.dialogs")
LOG.addHandler(logging.NullHandler())


class InputConfirmationDialogScene(Scene):
    """Input Confirmation Dialog Scene."""

    log = LOG
    NAME = "InputConfirmationDialog"
    DIALOG_TEXT = "Would you like to do a thing?"
    CONFIRMATION_TEXT = "Confirm"
    CANCEL_TEXT = "Cancel"
    VERSION = ""

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
            # Create a new LayeredDirty group specifically for the dialog
            groups = pygame.sprite.LayeredDirty()

        super().__init__(options=options, groups=groups)
        self.previous_scene = previous_scene

        # Create dialog with its own sprite group
        dialog_width = self.screen_width // 2
        dialog_height = self.screen_height // 2

        self.dialog = InputDialog(
            name=self.NAME,
            dialog_text=self.DIALOG_TEXT,  # Use this instance's DIALOG_TEXT
            confirm_text=self.CONFIRMATION_TEXT,
            cancel_text=self.CANCEL_TEXT,
            x=self.screen.get_rect().center[0] - (dialog_width // 2),
            y=self.screen.get_rect().center[1] - (dialog_height // 2),
            width=dialog_width,
            height=dialog_height,
            parent=self,
            groups=self.all_sprites,
        )
        # Set the dialog text
        # Use this instance's DIALOG_TEXT
        self.dialog.dialog_text_sprite.text_box.text = self.DIALOG_TEXT
        self.dialog.dialog_text_sprite.border_width = 0

    def setup(self: Self) -> None:
        """Set up the scene.

        Args:
            None

        Returns:
            None

        Raises:
            None

        """
        self.dialog.cancel_button.callbacks = {
            "on_left_mouse_button_up_event": self.on_cancel_event
        }
        self.dialog.confirm_button.callbacks = {
            "on_left_mouse_button_up_event": self.on_confirm_event
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
        # Set next scene before cleanup
        self.previous_scene.next_scene = self.previous_scene
        self.next_scene = self.previous_scene

        # Clear all sprites from our group
        self.all_sprites.empty()

        # Force the previous scene to redraw completely
        for sprite in self.previous_scene.all_sprites:
            sprite.dirty = 1

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
        self.log.info(f"Cancel: event: {event}, trigger: {trigger}")
        self.dismiss()

    def on_confirm_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle confirm events."""
        self.log.info(f"Confirm: event: {event}, trigger: {trigger}")
        # Get the text from input box before dismissing
        filename = self.dialog.input_box.text
        # Dismiss first to restore previous scene
        self.dismiss()
        # Then trigger appropriate canvas event based on dialog type
        if isinstance(self, SaveDialogScene):
            self.previous_scene.canvas.on_save_file_event(filename)
        elif isinstance(self, LoadDialogScene):
            self.previous_scene.canvas.on_load_file_event(filename)
        elif isinstance(self, NewCanvasDialogScene):
            self.previous_scene.canvas.on_new_file_event(filename)

    def on_input_box_submit_event(self: Self, control: object) -> None:
        """Handle the input box submit event.

        Args:
            control (object): The control object.

        Returns:
            None

        Raises:
            None

        """
        self.log.info(f"{self.name} Got text input from: {control.name}: {control.text}")

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
    NAME = "New Canvas Dialog"
    DIALOG_TEXT = "Enter canvas size (WxH):"
    CONFIRMATION_TEXT = "Create"
    CANCEL_TEXT = "Cancel"

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
        self.log.info(f"New Canvas: event: {event}, trigger: {trigger}")
        # Extract the text from the input box
        dimensions = self.dialog.input_box.text
        self.log.info(f"New Canvas dimensions: {dimensions}")
        self.log.info(f"Calling scene.on_new_file_event with dimensions: {dimensions}")
        self.previous_scene.on_new_file_event(dimensions)
        self.log.info("Scene.on_new_file_event completed")
        self.dismiss()


class LoadDialogScene(InputConfirmationDialogScene):
    """Load Dialog Scene."""

    log = LOG
    NAME = "Load Dialog"
    DIALOG_TEXT = "Enter filename to load:"
    CONFIRMATION_TEXT = "Load"
    CANCEL_TEXT = "Cancel"
    VERSION = ""

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
        self.log.info(f"Load File: event: {event}, trigger: {trigger}")
        self.previous_scene.canvas.on_load_file_event(self.dialog.input_box, self.dialog.input_box)
        self.dismiss()


class SaveDialogScene(InputConfirmationDialogScene):
    """Save Dialog Scene."""

    log = LOG
    NAME = "Save Dialog"
    DIALOG_TEXT = "Enter filename to save:"
    CONFIRMATION_TEXT = "Save"
    CANCEL_TEXT = "Cancel"
    VERSION = ""

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
        self.log.info(f"Save File: event: {event}, trigger: {trigger}")
        # Get the filename from the input box
        filename = self.dialog.input_box.text
        # Call save with just the filename
        self.previous_scene.canvas.on_save_file_event(filename)
        self.dismiss()
