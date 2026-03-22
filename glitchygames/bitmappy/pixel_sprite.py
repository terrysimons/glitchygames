"""BitmapPixelSprite — individual pixel representation on the editor canvas."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self, override

import pygame

from glitchygames.color import RGB_COMPONENT_COUNT
from glitchygames.sprites import BitmappySprite

if TYPE_CHECKING:
    from glitchygames import events

from .constants import LOG


class BitmapPixelSprite(BitmappySprite):
    """Bitmap Pixel Sprite."""

    log = LOG
    PIXEL_CACHE: ClassVar[dict[tuple[tuple[int, ...], int], pygame.Surface]] = {}

    def __init__(
        self: Self,
        x: int = 0,
        y: int = 0,
        width: int = 1,
        height: int = 1,
        name: str | None = None,
        pixel_number: int = 0,
        border_thickness: int = 1,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize the Bitmap Pixel Sprite."""
        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)  # type: ignore[arg-type]

        self.pixel_number = pixel_number
        self.pixel_width = width
        self.pixel_height = height
        self.border_thickness = border_thickness
        self.color = (96, 96, 96)
        self.pixel_color = (0, 0, 0, 255)
        self.x = x
        self.y = y

        self.rect = pygame.draw.rect(
            self.image, self.color, (self.x, self.y, self.width, self.height), self.border_thickness
        )

    @property
    def pixel_color(self: Self) -> tuple[int, int, int, int]:
        """Get the pixel color.

        Args:
            None

        Returns:
            tuple[int, int, int, int]: The pixel color with alpha.

        Raises:
            None

        """
        return self._pixel_color  # ty: ignore[invalid-return-type]

    @pixel_color.setter
    def pixel_color(
        self: Self, new_pixel_color: tuple[int, int, int] | tuple[int, int, int, int]
    ) -> None:
        """Set the pixel color.

        Args:
            new_pixel_color (tuple): The new pixel color (RGB or RGBA).

        Raises:
            None

        """
        # Convert RGB to RGBA if needed
        if len(new_pixel_color) == RGB_COMPONENT_COUNT:
            self._pixel_color = (new_pixel_color[0], new_pixel_color[1], new_pixel_color[2], 255)
        else:
            self._pixel_color = new_pixel_color
        self.dirty = 1

    @override
    def update(self: Self) -> None:
        """Update the sprite.

        Args:
            None

        Raises:
            None

        """
        cache_key = (self.pixel_color, self.border_thickness)
        cached_image = BitmapPixelSprite.PIXEL_CACHE.get(cache_key)

        if not cached_image:
            self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.image.fill((0, 0, 0, 0))  # Start with transparent

            # Draw main pixel
            pygame.draw.rect(self.image, self.pixel_color, (0, 0, self.width, self.height))

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

    def on_pixel_update_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the pixel update event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        if self.callbacks:
            callback = self.callbacks.get('on_pixel_update_event', None)

            if callback:
                callback(event=event, trigger=self)

    @override
    def on_left_mouse_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the left mouse button down event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        self.dirty = 1
        self.on_pixel_update_event(event)
