#!/usr/bin/env python3
"""Sprite Stack prototype script.

This module now uses the official animated sprite implementations
from glitchygames.sprites.animated.
"""

import abc
import argparse
import logging
from typing import Self, override

import pygame

# Import the official animated sprite classes
from glitchygames.sprites import SpriteFrame

# For cached objects look at:
# https://docs.python.org/dev/faq/programming.html#faq-cache-method-calls
#
# For fonts we probably want to use


class SpriteStackInterface(abc.ABC):
    """A formal interface for the Sprite Stack prototype."""

    log = logging.getLogger('glitchygames.sprite_stack.SpriteStackInterface')

    @classmethod
    @override
    def __subclasshook__(cls: type[Self], subclass: type) -> bool:
        """Override the default __subclasshook__ to create an interface.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        # Note: This accounts for under/dunder methods in addition to regular methods.
        interface_attributes: frozenset[str] = cls.__abstractmethods__

        # Check if subclass has __abstractmethods__ attribute
        subclass_attributes: frozenset[str] = getattr(subclass, '__abstractmethods__', frozenset())

        methods: list[bool] = []
        for attribute in sorted(interface_attributes):
            if hasattr(subclass, attribute) and attribute not in subclass_attributes:
                if callable(getattr(subclass, attribute)):
                    cls.log.info(f'{subclass.__name__}.{attribute} -> ✅ (callable)')
                else:
                    cls.log.info(f'{subclass.__name__}.{attribute} -> ✅ (attribute))')
                methods.append(True)
            else:
                cls.log.info(f'{subclass.__name__}.{attribute} -> ❌ (unimplemented)')
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
    def __getitem__(self: Self, index: int) -> 'SpriteFrame':
        """Return a sprite from the stack."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_size(self: Self) -> tuple[int, int]:
        """Return the size of the surface."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_alpha(self: Self) -> int | None:
        """Return the alpha value of the surface."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_colorkey(self: Self) -> tuple[int, int, int, int] | None:
        """Return the colorkey of the surface."""
        raise NotImplementedError


# SpriteFrame is now imported from glitchygames.sprites


class SpriteStack(SpriteStackInterface):
    """A prototype Sprite Stack class."""

    def __init__(self: Self, sprites: list['SpriteFrame'] | list[pygame.Surface]) -> None:
        """Initialize the Sprite Stack prototype."""
        super().__init__()
        self.stack: list[SpriteFrame] = []
        self.frame_index: int = 0

        for sprite in sprites:
            if isinstance(sprite, SpriteFrame):
                self.stack.append(sprite)
            else:
                self.stack.append(SpriteFrame(sprite))

    @property
    @override
    def image(self: Self) -> pygame.Surface:
        """Return the flattened sprite stack image."""
        return self.stack[self.frame_index].image

    @image.setter
    def image(self: Self, new_image: pygame.Surface) -> None:
        """Set the image."""
        self.stack[self.frame_index].image = new_image

    @property
    @override
    def rect(self: Self) -> pygame.Rect:
        """Return the sprite stack pygame.Rect."""
        return self.stack[self.frame_index].rect

    @rect.setter
    def rect(self: Self, new_rect: pygame.Rect) -> None:
        """Set the rect."""
        self.stack[self.frame_index].rect = new_rect

    @override
    def __getitem__(self: Self, index: int) -> 'SpriteFrame':
        """Return a sprite from the stack.

        Returns:
            'SpriteFrame': The item at the given index.

        """
        return self.stack[index]

    @override
    def get_size(self: Self) -> tuple[int, int]:
        """Return the size of the surface.

        Returns:
            tuple[int, int]: The size.

        """
        return self.stack[self.frame_index].get_size()

    @override
    def get_alpha(self: Self) -> int | None:
        """Return the alpha value of the surface.

        Returns:
            int | None: The alpha.

        """
        return self.stack[self.frame_index].get_alpha()

    @override
    def get_colorkey(self: Self) -> tuple[int, int, int, int] | None:
        """Return the colorkey of the surface.

        Returns:
            tuple[int, int, int, int] | None: The colorkey.

        """
        return self.stack[self.frame_index].get_colorkey()


# AnimatedSpriteInterface and AnimatedSprite are now imported from glitchygames.sprites
# The official implementations are used instead of the old incomplete ones


if __name__ == '__main__':
    parser = argparse.ArgumentParser('Sprite Stack Prototype')
    logging.getLogger('glitchygames.sprite_stack')
    logging.basicConfig(
        format='%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s',
        level=logging.DEBUG,
    )

    assert issubclass(SpriteStack, SpriteStackInterface), (
        'SpriteStack must implement SpriteStackInterface'
    )

    sprite_stack = SpriteStack([pygame.Surface((32, 32)) for _ in range(10)])
