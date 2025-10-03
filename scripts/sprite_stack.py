#!/usr/bin/env python3
"""Sprite Stack prototype script.

This module now uses the official animated sprite implementations
from glitchygames.sprites.animated.
"""

import abc
import argparse
import logging
from typing import Self

import pygame

# Import the official animated sprite classes
from glitchygames.sprites import SpriteFrame

# For cached objects look at:
# https://docs.python.org/dev/faq/programming.html#faq-cache-method-calls
#
# For fonts we probably want to use


class SpriteStackInterface(abc.ABC):
    """A formal interface for the Sprite Stack prototype."""

    log = logging.getLogger("glitchygames.sprite_stack.SpriteStackInterface")

    """A formal interface for the Sprite Stack prototype."""

    @classmethod
    def __subclasshook__(cls: Self, subclass: object) -> bool:
        """Override the default __subclasshook__ to create an interface."""
        # Note: This accounts for under/dunder methods in addition to regular methods.
        interface_attributes = set(cls.__abstractmethods__)

        # Check if subclass has __abstractmethods__ attribute
        if hasattr(subclass, "__abstractmethods__"):
            subclass_attributes = set(subclass.__abstractmethods__)
        else:
            subclass_attributes = set()

        methods = []
        for attribute in sorted(interface_attributes):
            if hasattr(subclass, attribute) and attribute not in subclass_attributes:
                if callable(getattr(subclass, attribute)):
                    cls.log.info(f"{subclass.__name__}.{attribute} -> ✅ (callable)")
                else:
                    cls.log.info(f"{subclass.__name__}.{attribute} -> ✅ (attribute))")
                methods.append(True)
            else:
                cls.log.info(f"{subclass.__name__}.{attribute} -> ❌ (unimplemented)")
                methods.append(False)

        # all([]) returns True, so mask it
        #
        # This protects against an empty attribute list
        return False if not interface_attributes else all(methods)

    @property
    @abc.abstractmethod
    def image(self: Self) -> pygame.Surface:
        """Return a pygame.Surface."""
        raise NotImplementedError

    @image.setter
    @abc.abstractmethod
    def image(self: Self, new_image: pygame.Surface) -> None:
        """Set the image."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def rect(self: Self) -> pygame.Rect:
        """Return a pygame.Rect."""
        raise NotImplementedError

    @rect.setter
    @abc.abstractmethod
    def rect(self: Self, new_rect: pygame.Rect) -> None:
        """Set the rect."""
        raise NotImplementedError

    @abc.abstractmethod
    def __getitem__(self: Self, index: int) -> "SpriteFrame":
        """Return a sprite from the stack."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_size(self: Self) -> tuple[int, int]:
        """Return the size of the surface."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_alpha(self: Self) -> int:
        """Return the alpha value of the surface."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_colorkey(self: Self) -> int | None:
        """Return the colorkey of the surface."""
        raise NotImplementedError


# SpriteFrame is now imported from glitchygames.sprites


class SpriteStack(SpriteStackInterface):
    """A prototype Sprite Stack class."""

    def __init__(self: Self, sprites: list["SpriteFrame"] | list[pygame.Surface]) -> Self:
        """Initialize the Sprite Stack prototype."""
        super().__init__()
        self.stack = []
        self.frame_index = 0

        for sprite in sprites:
            if isinstance(sprite, SpriteFrame):
                self.stack.append(sprite)
            else:
                self.stack.append(SpriteFrame(sprite))

    @property
    def image(self: Self) -> pygame.Surface:
        """Return the flattened sprite stack image."""
        return self.stack[self.frame_index].image

    @image.setter
    def image(self: Self, new_image: pygame.Surface) -> None:
        """Set the image."""
        self.stack[self.frame_index].image = new_image

    @property
    def rect(self: Self) -> pygame.Rect:
        """Return the sprite stack pygame.Rect."""
        return self.stack[self.frame_index].rect

    @rect.setter
    def rect(self: Self, new_rect: pygame.Rect) -> None:
        """Set the rect."""
        self.stack[self.frame_index].rect = new_rect

    def __getitem__(self: Self, index: int) -> "SpriteFrame":
        """Return a sprite from the stack."""
        return self.stack[index]

    def get_size(self: Self) -> tuple[int, int]:
        """Return the size of the surface."""
        return self.stack[self.frame_index].get_size()

    def get_alpha(self: Self) -> int:
        """Return the alpha value of the surface."""
        return self.stack[self.frame_index].get_alpha()

    def get_colorkey(self: Self) -> int | None:
        """Return the colorkey of the surface."""
        return self.stack[self.frame_index].get_colorkey()


# AnimatedSpriteInterface and AnimatedSprite are now imported from glitchygames.sprites
# The official implementations are used instead of the old incomplete ones


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Sprite Stack Prototype")
    logging.getLogger("glitchygames.sprite_stack")
    logging.basicConfig(
        format="%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s",
        level=logging.DEBUG,
    )

    assert issubclass(SpriteStack, SpriteStackInterface)

    sprite_stack = SpriteStack([pygame.Surface((32, 32)) for _ in range(10)])
