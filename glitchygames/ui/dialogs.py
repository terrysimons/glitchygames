#!/usr/bin/env python3
"""Dialog scene classes for GlitchyGames UI.

This module contains dialog scene classes that provide input dialogs
for various operations like saving, loading, and creating new files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Self

import sys
import pygame
from glitchygames.scenes import Scene
from glitchygames.ui import InputDialog

LOG = logging.getLogger("game.ui.dialogs")
LOG.addHandler(logging.NullHandler())


def _process_example_filename(filename: str) -> tuple[str, bool]:
    """Process filename that may contain 'example:' or 'examples:' prefix.
    
    If the filename contains 'example:' or 'examples:', strip it off and return the cleaned
    filename along with a flag indicating it should be saved to the examples
    directory.
    
    Args:
        filename: The input filename that may contain 'example:' or 'examples:' prefix
        
    Returns:
        tuple: (cleaned_filename, is_example) where is_example is True if
               the filename had 'example:' or 'examples:' prefix
    """
    is_example = False
    cleaned_filename = filename.strip()
    
    if cleaned_filename.startswith("example:"):
        is_example = True
        cleaned_filename = cleaned_filename[len("example:"):].strip()
        LOG.info(f"Detected 'example:' prefix. Cleaning filename: '{filename}' -> '{cleaned_filename}'")
    elif cleaned_filename.startswith("examples:"):
        is_example = True
        cleaned_filename = cleaned_filename[len("examples:"):].strip()
        LOG.info(f"Detected 'examples:' prefix. Cleaning filename: '{filename}' -> '{cleaned_filename}'")
    
    return cleaned_filename, is_example


def _get_examples_dir() -> Path:
    """Get the path to the examples/resources/sprites directory.
    
    Returns:
        Path: Path to the examples sprites directory
    """
    # Use the same logic as resource_path but defined here to avoid circular imports
    if hasattr(sys, "_MEIPASS"):
        # Running in PyInstaller bundle
        base_path = Path(sys._MEIPASS)
        return base_path.joinpath("glitchygames", "examples", "resources", "sprites")
    # Running in normal Python environment
    # dialogs.py is in glitchygames/ui, so go up to glitchygames/, then to examples/
    # Path(__file__) = glitchygames/ui/dialogs.py
    # .parent = glitchygames/ui/
    # .parent.parent = glitchygames/
    # Then join with examples/resources/sprites
    return Path(__file__).parent.parent.joinpath("examples", "resources", "sprites")


def _get_save_path(filename: str) -> Path:
    """Get the full save path for a filename.
    
    Args:
        filename: The filename (may contain 'example:' or 'examples:' prefix)
        
    Returns:
        Path: Full path where the file should be saved
    """
    cleaned_filename, is_example = _process_example_filename(filename)
    
    if is_example:
        examples_dir = _get_examples_dir()
        save_path = examples_dir / cleaned_filename
        LOG.info(f"Example save path: {save_path}")
        return save_path
    else:
        # Normal save - return just the filename (current behavior)
        save_path = Path(cleaned_filename)
        LOG.info(f"Normal save path: {save_path}")
        return save_path


def _get_load_path(filename: str) -> Path:
    """Get the full load path for a filename.
    
    Args:
        filename: The filename (may contain 'example:' or 'examples:' prefix)
        
    Returns:
        Path: Full path where the file should be loaded from
    """
    cleaned_filename, is_example = _process_example_filename(filename)
    
    if is_example:
        examples_dir = _get_examples_dir()
        load_path = examples_dir / cleaned_filename
        LOG.info(f"Example load path: {load_path}")
        return load_path
    else:
        # Normal load - return just the filename (current behavior)
        load_path = Path(cleaned_filename)
        LOG.info(f"Normal load path: {load_path}")
        return load_path


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
            print(f"DEBUG: Dialog calling canvas.on_load_file_event with filename: {filename}")
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
        # Get the filename from the input box text
        filename = self.dialog.input_box.text
        # Process example: prefix if present
        load_path = _get_load_path(filename)
        LOG.info(f"Processed load path: {load_path}")
        # Pass the path as string to maintain compatibility
        self.previous_scene.canvas.on_load_file_event(str(load_path))
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
        # Process example: prefix if present
        save_path = _get_save_path(filename)
        LOG.info(f"Processed save path: {save_path}")
        # Pass the path as string to maintain compatibility
        self.previous_scene.canvas.on_save_file_event(str(save_path))
        self.dismiss()


class DeleteAnimationDialogScene(Scene):
    """Delete Animation Confirmation Dialog - requires typing exact name."""

    log = LOG
    NAME = "DeleteAnimationDialog"

    def __init__(
        self,
        previous_scene: Scene,
        animation_name: str,
        on_confirm_callback,
        on_cancel_callback=None,
        options: dict | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ):
        """Initialize the Delete Animation Dialog Scene.

        Args:
            previous_scene: The previous scene to return to
            animation_name: The name of the animation to delete
            on_confirm_callback: Function to call when user confirms
            on_cancel_callback: Function to call when user cancels (optional)
            options: Options for the scene
            groups: Sprite groups
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(options=options, groups=groups)
        self.previous_scene = previous_scene
        self.animation_name = animation_name
        self.on_confirm_callback = on_confirm_callback
        self.on_cancel_callback = on_cancel_callback

        # Create dialog
        dialog_width = 500
        dialog_height = 200

        message = f"Type '{animation_name}' to confirm deletion:"

        self.dialog = InputDialog(
            name=self.NAME,
            dialog_text=message,
            confirm_text="Delete",
            cancel_text="Cancel",
            x=self.screen.get_rect().center[0] - (dialog_width // 2),
            y=self.screen.get_rect().center[1] - (dialog_height // 2),
            width=dialog_width,
            height=dialog_height,
            parent=self,
            groups=self.all_sprites,
        )
        self.dialog.dialog_text_sprite.text_box.text = message
        self.dialog.dialog_text_sprite.border_width = 0

    def setup(self):
        """Set up the scene."""
        self.dialog.cancel_button.callbacks = {
            "on_left_mouse_button_up_event": self.on_cancel_event
        }
        self.dialog.confirm_button.callbacks = {
            "on_left_mouse_button_up_event": self.on_confirm_event
        }
        self.dialog.add(self.all_sprites)
        # Activate input box so user can start typing immediately
        self.dialog.input_box.activate()

    def on_confirm_event(self, event: pygame.event.Event, trigger: object = None):
        """Handle confirm button click."""
        # Get the typed text
        typed_text = self.dialog.input_box.text.strip()

        # Validate that the typed text matches the animation name
        if typed_text == self.animation_name:
            LOG.info(f"DeleteAnimationDialog: User confirmed deletion of '{self.animation_name}'")
            # Call the callback if provided
            if self.on_confirm_callback:
                self.on_confirm_callback()
            # Return to previous scene
            self.game_engine.scene_manager.switch_to_scene(self.previous_scene)
        else:
            LOG.warning(f"DeleteAnimationDialog: Typed name '{typed_text}' does not match '{self.animation_name}'")
            # Could show an error message here, but for now just do nothing
            # Clear the input box to let user try again
            self.dialog.input_box.text = ""

    def on_cancel_event(self, event: pygame.event.Event, trigger: object = None):
        """Handle cancel button click."""
        LOG.info("DeleteAnimationDialog: User cancelled")
        # Call the cancel callback if provided
        if self.on_cancel_callback:
            self.on_cancel_callback()
        # Return to previous scene
        self.game_engine.scene_manager.switch_to_scene(self.previous_scene)

    def on_key_down_event(self, event: pygame.event.Event) -> None:
        """Handle the key down event."""
        if self.dialog.input_box.active:
            self.dialog.on_key_down_event(event)
        else:
            super().on_key_down_event(event)

    def on_key_up_event(self, event: pygame.event.Event) -> None:
        """Handle the key up event."""
        if self.dialog.input_box.active:
            self.dialog.on_key_up_event(event)
        elif event.key == pygame.K_TAB:
            self.dialog.input_box.activate()
        else:
            super().on_key_up_event(event)


class DeleteFrameDialogScene(Scene):
    """Delete Frame Confirmation Dialog - requires typing 'YES'."""

    log = LOG
    NAME = "DeleteFrameDialog"

    def __init__(
        self,
        previous_scene: Scene,
        animation_name: str,
        frame_index: int,
        on_confirm_callback,
        on_cancel_callback=None,
        options: dict | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ):
        """Initialize the Delete Frame Dialog Scene.

        Args:
            previous_scene: The previous scene to return to
            animation_name: The name of the animation containing the frame
            frame_index: The index of the frame to delete
            on_confirm_callback: Function to call when user confirms
            on_cancel_callback: Function to call when user cancels (optional)
            options: Options for the scene
            groups: Sprite groups
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(options=options, groups=groups)
        self.previous_scene = previous_scene
        self.animation_name = animation_name
        self.frame_index = frame_index
        self.on_confirm_callback = on_confirm_callback
        self.on_cancel_callback = on_cancel_callback

        # Create dialog
        dialog_width = 500
        dialog_height = 200

        message1 = f"Delete this frame from '{animation_name}'?"
        message2 = "Type 'YES' to confirm:"

        self.dialog = InputDialog(
            name=self.NAME,
            dialog_text=message1,
            confirm_text="Delete",
            cancel_text="Cancel",
            x=self.screen.get_rect().center[0] - (dialog_width // 2),
            y=self.screen.get_rect().center[1] - (dialog_height // 2),
            width=dialog_width,
            height=dialog_height,
            parent=self,
            groups=self.all_sprites,
        )
        self.dialog.dialog_text_sprite.text_box.text = message1
        self.dialog.dialog_text_sprite.border_width = 0

        # Add second label for the confirmation prompt
        from glitchygames.ui import TextSprite
        self.second_label = TextSprite(
            text=message2,
            x=self.dialog.dialog_text_sprite.rect.x,
            y=self.dialog.dialog_text_sprite.rect.y + 30,  # Position below first label
            width=self.dialog.dialog_text_sprite.rect.width,
            height=20,
            groups=self.all_sprites
        )
        self.second_label.border_width = 0
        self.second_label.background_color = self.dialog.dialog_text_sprite.background_color

    def setup(self):
        """Set up the scene."""
        self.dialog.cancel_button.callbacks = {
            "on_left_mouse_button_up_event": self.on_cancel_event
        }
        self.dialog.confirm_button.callbacks = {
            "on_left_mouse_button_up_event": self.on_confirm_event
        }
        self.dialog.add(self.all_sprites)
        # Activate input box so user can start typing immediately
        self.dialog.input_box.activate()

    def on_confirm_event(self, event: pygame.event.Event, trigger: object = None):
        """Handle confirm button click."""
        # Get the typed text
        typed_text = self.dialog.input_box.text.strip()

        # Validate that the typed text is "YES"
        if typed_text == "YES":
            LOG.info(f"DeleteFrameDialog: User confirmed deletion of frame {self.frame_index} from '{self.animation_name}'")
            # Call the callback if provided
            if self.on_confirm_callback:
                self.on_confirm_callback()
            # Return to previous scene
            self.game_engine.scene_manager.switch_to_scene(self.previous_scene)
        else:
            LOG.warning(f"DeleteFrameDialog: Typed text '{typed_text}' does not match 'YES'")
            # Clear the input box to let user try again
            self.dialog.input_box.text = ""

    def on_cancel_event(self, event: pygame.event.Event, trigger: object = None):
        """Handle cancel button click."""
        LOG.info("DeleteFrameDialog: User cancelled")
        # Call the cancel callback if provided
        if self.on_cancel_callback:
            self.on_cancel_callback()
        # Return to previous scene
        self.game_engine.scene_manager.switch_to_scene(self.previous_scene)

    def on_key_down_event(self, event: pygame.event.Event) -> None:
        """Handle the key down event."""
        if self.dialog.input_box.active:
            self.dialog.on_key_down_event(event)
        else:
            super().on_key_down_event(event)

    def on_key_up_event(self, event: pygame.event.Event) -> None:
        """Handle the key up event."""
        if self.dialog.input_box.active:
            self.dialog.on_key_up_event(event)
        elif event.key == pygame.K_TAB:
            self.dialog.input_box.activate()
        else:
            super().on_key_up_event(event)
