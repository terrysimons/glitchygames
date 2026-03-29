"""GlitchyGames UI input and dialog components.

This module contains the InputBox, InputDialog, and ConfirmDialog widget classes.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Self, override

import pygame
from pygame import Rect

from glitchygames.fonts import FontManager, GameFont
from glitchygames.sprites import (
    BitmappySprite,
    Sprite,
)
from glitchygames.ui.buttons import ButtonSprite
from glitchygames.ui.text_widgets import TextBoxSprite

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Protocol

    from glitchygames.events.base import HashableEvent

    class RectProtocol(Protocol):
        """Parent that exposes a rect for positioning."""

        rect: pygame.Rect
        x: int
        y: int

    class DialogProtocol(Protocol):
        """Parent that handles confirm/cancel events."""

        def on_confirm_event(self, event: HashableEvent, trigger: HashableEvent) -> None:
            """Handle dialog confirmation events."""
            ...

        def on_cancel_event(self, event: HashableEvent, trigger: HashableEvent) -> None:
            """Handle dialog cancellation events."""
            ...


LOG = logging.getLogger('game.ui')
LOG.addHandler(logging.NullHandler())

CURSOR_BLINK_HALF_SECOND = 0.5


class InputBox(Sprite):
    """An input box class."""

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        color: tuple[int, ...] = (233, 248, 215),
        text: str = '',
        name: str | None = None,
        parent: RectProtocol | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize an InputBox.

        Args:
            x (int): The x coordinate of the input box.
            y (int): The y coordinate of the input box.
            width (int): The width of the input box.
            height (int): The height of the input box.
            color (tuple): The color of the input box.
            text (str): The text to display in the input box.
            name (str): The name of the input box.
            parent (object): The parent object.
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups to add the sprite to.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)
        pygame.font.init()
        self.offset_x: int = self.parent.x if self.parent else 0
        self.offset_y: int = self.parent.y if self.parent else 0
        self.rect.x = x + self.offset_x
        self.rect.y = y + self.offset_y
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.font = pygame.font.SysFont('Times', 14)
        self.text = text
        self.text_image = self.font.render(self.text, True, self.color)  # noqa: FBT003
        self.is_active = False
        self.image = pygame.Surface((self.width, self.height))
        self.image.convert()
        self.parent = parent
        self.cursor_rect = self.text_image.get_rect()

        self.cursor = pygame.Rect(self.cursor_rect.topright, (3, self.cursor_rect.height))

        self.dirty = 2

    def activate(self: Self) -> None:
        """Activate the input box.

        Args:
            None

        """
        self.is_active = True
        self.dirty = 2

    def deactivate(self: Self) -> None:
        """Deactivate the input box.

        Args:
            None

        """
        self.is_active = False
        self.dirty = 0

    def on_input_box_submit_event(self: Self, _event: HashableEvent) -> None:
        """Handle input box submit events.

        Args:
            _event (pygame.event.Event): The event to handle.

        """
        if self.parent:
            callback = getattr(self.parent, 'on_input_box_submit_event', None)
            if callback:
                callback(event=self)
            else:
                self.log.info(f'{self.name}: Submitted "{self.text}" but no parent is configured.')

    @override
    def update(self: Self) -> None:
        """Update the input box.

        Args:
            None

        """
        self.image.fill((0, 0, 0))
        self.image.blit(self.text_image, (4, 4))

        pygame.draw.rect(self.image, self.color, (0, 0, self.rect.width, self.rect.height), 1)

        # Blit the  cursor
        if time.time() % 1 > CURSOR_BLINK_HALF_SECOND and self.is_active:
            self.cursor_rect = self.text_image.get_rect(topleft=(5, 2))

            self.cursor.midleft = self.cursor_rect.midright

            pygame.draw.rect(self.image, self.color, self.cursor)

    @override
    def render(self: Self, screen: pygame.Surface | None = None) -> None:
        """Render the input box.

        Args:
            screen (pygame.Surface | None): The surface to render to.

        """
        self.text_image = self.font.render(self.text, True, (255, 255, 255))  # noqa: FBT003

    def on_mouse_up_event(self: Self, _event: HashableEvent) -> None:
        """Handle mouse up events.

        Args:
            _event (pygame.event.Event): The event to handle.

        """
        self.activate()

    @override
    def on_key_up_event(self: Self, event: HashableEvent) -> None:
        """Handle key up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.info('INPUT BOX EVENT: %s', event)
        if self.is_active:
            pygame.key.set_repeat(200)

            if event.key in {pygame.K_TAB, pygame.K_ESCAPE}:
                self.deactivate()

    @override
    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Handle key down events."""
        if self.is_active:
            if event.key == pygame.K_RETURN:
                # Trigger confirm button instead of adding newline
                on_confirm = getattr(self.parent, 'on_confirm_event', None)
                if on_confirm:
                    on_confirm(event=event, trigger=self)
            else:
                # Handle other key input
                if event.key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]
                # Handle colon character - check key combination first, then unicode
                elif event.key == pygame.K_SEMICOLON and (event.mod & pygame.KMOD_SHIFT):
                    # Shift+; produces colon (:) - handle case where unicode might not be set
                    self.text += ':'
                elif event.unicode:
                    # Use unicode if available
                    self.text += event.unicode
                self.render()


class InputDialog(BitmappySprite):
    """An input dialog class."""

    log = LOG

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        name: str | None = None,
        dialog_text: str = 'Would you like to do a thing?',
        confirm_text: str = 'Confirm',
        cancel_text: str = 'Cancel',
        _callbacks: Callable[..., Any] | None = None,
        parent: DialogProtocol | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize an InputDialog.

        Args:
            x (int): The x coordinate of the input dialog.
            y (int): The y coordinate of the input dialog.
            width (int): The width of the input dialog.
            height (int): The height of the input dialog.
            name (str): The name of the input dialog.
            dialog_text (str): The text to display in the dialog.
            confirm_text (str): The text to display on the confirm button.
            cancel_text (str): The text to display on the cancel button.
            _callbacks (Callable): The callbacks to call when events occur.
            parent (object): The parent object.
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups to add the sprite to.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            parent=parent,
            groups=groups,
        )

        # Set border width
        self.border_width = 1

        # Create a black background surface
        self.image = pygame.Surface((width, height))
        self.image.fill((0, 0, 0))

        # Position dialog text at top
        self.dialog_text_sprite = TextBoxSprite(
            name='dialog_text',
            x=x + 20,
            y=y + 20,
            width=width - 40,
            height=20,
            parent=self,
            groups=groups,
        )
        # Set the text after creation
        self.dialog_text_sprite.text_box.text = dialog_text

        # Position input box in middle
        self.input_box = InputBox(
            x=x + 20,
            y=y + (height // 2) - 10,  # Vertically centered
            width=width - 40,
            height=20,
            text='',
            parent=self,  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
            groups=groups,
        )

        # Position buttons at bottom
        button_y = y + height - 40  # 20px from bottom

        # Cancel on right
        self.cancel_button = ButtonSprite(
            name=cancel_text,
            x=x + width - 95,  # 20px from right edge
            y=button_y,
            width=75,
            height=20,
            parent=self,  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
            groups=groups,
        )

        # Confirm to left of cancel
        self.confirm_button = ButtonSprite(
            name=confirm_text,
            x=x + width - 180,  # 10px gap between buttons
            y=button_y,
            width=75,
            height=20,
            parent=self,  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
            groups=groups,
        )

        self.input_box.activate()

    @override
    def update_nested_sprites(self: Self) -> None:
        """Update the nested sprites.

        Args:
            None

        """
        self.cancel_button.dirty = self.dirty
        self.confirm_button.dirty = self.dirty

    @override
    def update(self: Self) -> None:
        """Update the input dialog."""
        # Clear the surface first
        self.image.fill((0, 0, 0))  # Black background

        # Draw the bounding box
        pygame.draw.rect(
            self.image,
            (128, 128, 128),
            Rect(0, 0, self.width, self.height),
            self.border_width,
        )

        # Mark components as dirty
        self.dialog_text_sprite.dirty = 1
        self.cancel_button.dirty = 1
        self.confirm_button.dirty = 1

        # Blit to self.image instead of self.screen
        self.image.blit(
            self.dialog_text_sprite.image,
            (
                self.dialog_text_sprite.rect.x - self.rect.x,
                self.dialog_text_sprite.rect.y - self.rect.y,
            ),
        )
        self.image.blit(
            self.cancel_button.image,
            (self.cancel_button.rect.x - self.rect.x, self.cancel_button.rect.y - self.rect.y),
        )
        self.image.blit(
            self.confirm_button.image,
            (self.confirm_button.rect.x - self.rect.x, self.confirm_button.rect.y - self.rect.y),
        )
        self.image.blit(
            self.input_box.image,
            (self.input_box.rect.x - self.rect.x, self.input_box.rect.y - self.rect.y),
        )

    def on_confirm_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle confirm events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        """
        if self.parent:
            self.parent.on_confirm_event(event=event, trigger=trigger)
        self.log.info(f'{self.name}: Got confirm event!')

    def on_cancel_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle cancel events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        """
        if self.parent:
            self.parent.on_cancel_event(event=event, trigger=trigger)
        self.log.info(f'{self.name}: Got cancel event!')

    def on_input_box_cancel_event(self: Self, control: object) -> None:
        """Handle input box cancel events.

        Args:
            control (object): The control that triggered the event.

        """
        control_name = getattr(control, 'name', '')
        control_text = getattr(control, 'text', '')
        self.log.info(f'{self.name} Got text input from: {control_name}: {control_text}')
        self.on_cancel_event(event=control, trigger=control)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]

    def on_input_box_submit_event(self: Self, event: HashableEvent) -> None:
        """Handle input box submit events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.info(f'{self.name} Got text input from: {event.name}: {event.text}')
        self.on_confirm_event(event=event, trigger=event)

    @override
    def on_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(f'{self.name} Got mouse button up event: {event}')
        # Only activate if click was within input box bounds
        if self.input_box.rect.collidepoint(event.pos):
            self.input_box.activate()
        else:
            self.input_box.deactivate()

    @override
    def on_key_up_event(self: Self, event: HashableEvent) -> None:
        """Handle key up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.info(f'Got Event: {event} from {self.parent}')

        if self.input_box.is_active:
            self.input_box.on_key_up_event(event)
        elif event.key == pygame.K_TAB:
            self.input_box.activate()
        else:
            super().on_key_up_event(event)

    @override
    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Handle key down events."""
        if event.key == pygame.K_TAB:
            self.input_box.activate()
        else:
            self.input_box.on_key_down_event(event)


class ConfirmDialog(BitmappySprite):
    """Confirmation dialog with Yes/No buttons."""

    def __init__(
        self,
        text: str,
        confirm_callback: Callable[[], None] | None,
        cancel_callback: Callable[[], None] | None,
        *,
        x: int = 0,
        y: int = 0,
        width: int = 300,
        height: int = 100,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize the confirmation dialog.

        Args:
            text: The confirmation message to display
            confirm_callback: Function to call when user confirms
            cancel_callback: Function to call when user cancels
            x: X position
            y: Y position
            width: Dialog width
            height: Dialog height
            groups: Sprite groups

        """
        super().__init__(x=x, y=y, width=width, height=height, groups=groups)

        self.text = text
        self.confirm_callback = confirm_callback
        self.cancel_callback = cancel_callback

        # Button dimensions
        button_width = 80
        button_height = 30
        button_spacing = 20
        button_y = height - button_height - 10

        # Calculate button positions (centered)
        total_button_width = (button_width * 2) + button_spacing
        buttons_start_x = (width - total_button_width) // 2

        # Create Yes button
        self.yes_button_rect = pygame.Rect(buttons_start_x, button_y, button_width, button_height)

        # Create No button
        self.no_button_rect = pygame.Rect(
            buttons_start_x + button_width + button_spacing,
            button_y,
            button_width,
            button_height,
        )

        self.hover_button = None  # Track which button is hovered

        self.dirty = 2

    @override
    def update(self, *args: object, **kwargs: object) -> None:
        """Update the dialog."""
        # Check mouse position for hover effects
        mouse_pos = pygame.mouse.get_pos()
        dialog_relative_x = mouse_pos[0] - self.rect.x
        dialog_relative_y = mouse_pos[1] - self.rect.y

        prev_hover = self.hover_button
        self.hover_button = None

        if self.yes_button_rect.collidepoint(dialog_relative_x, dialog_relative_y):
            self.hover_button = 'yes'
        elif self.no_button_rect.collidepoint(dialog_relative_x, dialog_relative_y):
            self.hover_button = 'no'

        if prev_hover != self.hover_button:
            self.dirty = 2

        # Render if dirty
        if self.dirty:
            self.render()

    @override
    def render(self, screen: pygame.Surface | None = None) -> None:
        """Render the confirmation dialog."""
        # Draw semi-transparent background
        self.image.fill((40, 40, 40))

        # Draw border
        pygame.draw.rect(self.image, (100, 100, 100), self.image.get_rect(), 2)

        # Render text
        font: GameFont = FontManager.get_font()
        text_surface = font.render(self.text, fgcolor=(255, 255, 255), size=14)
        if isinstance(text_surface, tuple):
            text_surface, text_rect = text_surface
        else:
            text_rect = text_surface.get_rect()

        text_rect.centerx = self.image.get_width() // 2  # ty: ignore[unresolved-attribute]
        text_rect.y = 20  # ty: ignore[unresolved-attribute]
        self.image.blit(text_surface, text_rect)  # ty: ignore[invalid-argument-type]

        # Draw Yes button
        yes_color = (60, 120, 60) if self.hover_button == 'yes' else (40, 100, 40)
        pygame.draw.rect(self.image, yes_color, self.yes_button_rect)
        pygame.draw.rect(self.image, (80, 140, 80), self.yes_button_rect, 2)

        yes_text = font.render('Yes', fgcolor=(255, 255, 255), size=12)
        if isinstance(yes_text, tuple):
            yes_text, yes_text_rect = yes_text
        else:
            yes_text_rect = yes_text.get_rect()
        yes_text_rect.center = self.yes_button_rect.center  # ty: ignore[unresolved-attribute]
        self.image.blit(yes_text, yes_text_rect)  # ty: ignore[invalid-argument-type]

        # Draw No button
        no_color = (120, 60, 60) if self.hover_button == 'no' else (100, 40, 40)
        pygame.draw.rect(self.image, no_color, self.no_button_rect)
        pygame.draw.rect(self.image, (140, 80, 80), self.no_button_rect, 2)

        no_text = font.render('No', fgcolor=(255, 255, 255), size=12)
        if isinstance(no_text, tuple):
            no_text, no_text_rect = no_text
        else:
            no_text_rect = no_text.get_rect()
        no_text_rect.center = self.no_button_rect.center  # ty: ignore[unresolved-attribute]
        self.image.blit(no_text, no_text_rect)  # ty: ignore[invalid-argument-type]

        self.dirty = 0

    def handle_mouse_down(self, pos: tuple[int, int]) -> bool:
        """Handle mouse down events.

        Args:
            pos: Mouse position relative to dialog

        Returns:
            True if event was handled

        """
        if self.yes_button_rect.collidepoint(pos):
            # User confirmed
            if self.confirm_callback:
                self.confirm_callback()
            self.kill()  # Remove dialog
            return True
        if self.no_button_rect.collidepoint(pos):
            # User cancelled
            if self.cancel_callback:
                self.cancel_callback()
            self.kill()  # Remove dialog
            return True

        return False
