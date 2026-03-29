"""GlitchyGames UI button and checkbox components.

This module contains the ButtonSprite and CheckboxSprite widget classes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self, override

import pygame
from pygame import Rect

from glitchygames.sprites import (
    BitmappySprite,
)
from glitchygames.ui.text_widgets import TextSprite

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Protocol

    from glitchygames.events.base import HashableEvent

    class RectProtocol(Protocol):
        """Parent that exposes a rect for positioning."""

        rect: pygame.Rect
        x: int
        y: int


LOG = logging.getLogger('game.ui')
LOG.addHandler(logging.NullHandler())


class ButtonSprite(BitmappySprite):
    """A button sprite class."""

    log = LOG

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        name: str | None = None,
        parent: RectProtocol | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize a ButtonSprite.

        Args:
            x (int): The x coordinate of the button sprite.
            y (int): The y coordinate of the button sprite.
            width (int): The width of the button sprite.
            height (int): The height of the button sprite.
            name (str): The name of the button sprite.
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
            focusable=True,
            parent=parent,
            groups=groups,
        )
        self.border_color = (255, 255, 255)
        self.active_color = (128, 128, 128)
        self.inactive_color = (0, 0, 0)
        self.background_color = self.inactive_color
        self.callbacks: dict[str, Any] = {}  # Initialize callbacks attribute

        self.text = TextSprite(
            background_color=self.background_color,
            x=self.parent.rect.centerx if parent else self.x,
            y=self.parent.rect.centery if parent else self.y,
            width=self.width,
            height=self.height,
            name=self.name,  # ty: ignore[invalid-argument-type]
            text=self.name,  # ty: ignore[invalid-argument-type]
            parent=self,
            groups=groups,
        )
        self.text.rect.center = self.rect.center

        pygame.draw.rect(self.image, self.border_color, Rect(0, 0, self.width, self.height), 1)

    @property
    def x(self: Self) -> int:
        """Get the x coordinate of the button sprite.

        Args:
            None

        Returns:
            int: The x coordinate of the button sprite.

        """
        return int(self.rect.x)

    @x.setter
    def x(self: Self, new_x: int) -> None:
        """Set the x coordinate of the button sprite.

        Args:
            new_x (int): The new x coordinate of the button sprite.

        """
        self.rect.x = new_x
        self.text.x = new_x  # Position relative to button
        self.dirty = 1

    @property
    def y(self: Self) -> int:
        """Get the y coordinate of the button sprite.

        Args:
            None

        Returns:
            int: The y coordinate of the button sprite.

        """
        return int(self.rect.y)

    @y.setter
    def y(self: Self, new_y: int) -> None:
        """Set the y coordinate of the button sprite.

        Args:
            new_y (int): The new y coordinate of the button sprite.

        """
        self.rect.y = new_y
        self.text.y = new_y  # Position relative to button
        self.dirty = 1

    @override
    def update_nested_sprites(self: Self) -> None:
        """Update the nested sprites.

        Sets the dirty flag on the nested sprites.

        Args:
            None

        """
        self.text.dirty = self.dirty

    @override
    def on_left_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        self.background_color = self.active_color
        super().on_left_mouse_button_down_event(event)
        self.dirty = 1

    @override
    def on_left_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        """
        self.background_color = self.inactive_color
        super().on_left_mouse_button_up_event(event)
        self.dirty = 1


class CheckboxSprite(ButtonSprite):
    """A checkbox sprite class."""

    log = LOG

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        name: str | None = None,
        _callbacks: Callable[..., Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize a CheckboxSprite.

        Args:
            x (int): The x coordinate of the checkbox sprite.
            y (int): The y coordinate of the checkbox sprite.
            width (int): The width of the checkbox sprite.
            height (int): The height of the checkbox sprite.
            name (str): The name of the checkbox sprite.
            _callbacks (Callable): The callbacks to call when events occur.
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups to add the sprite to.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)

        self.checked = False
        self.color = (128, 128, 128)

    @override
    def update(self: Self) -> None:
        """Update the checkbox sprite.

        Args:
            None

        """
        if not self.checked:
            self.image.fill((0, 0, 0))

        pygame.draw.rect(self.image, self.color, Rect(0, 0, self.width, self.height), 1)

        if self.checked:
            pygame.draw.line(self.image, self.color, (0, 0), (self.width - 1, self.height - 1), 1)
            pygame.draw.line(self.image, self.color, (0, self.height - 1), (self.width - 1, 0), 1)

    @override
    def on_left_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """

    @override
    def on_left_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.checked = not self.checked
        self.dirty = 1
