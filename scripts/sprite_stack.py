#!/usr/bin/env python3
"""Sprite Stack prototype script."""

import abc
import argparse
import logging
from typing import Self

import pygame

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
        subclass_attributes = set(subclass.__abstractmethods__)

        interface_is_implemented = False
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
        # which would be a misconfiguration of the interface
        if len(methods) > 0 and all(methods):
            interface_is_implemented = all(methods)

        return interface_is_implemented

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
    def __getitem__(self: Self, index: int) -> pygame.Surface:
        """Return a sprite from the stack."""
        raise NotImplementedError

    @abc.abstractmethod
    def intentionally_missing_method(self: Self) -> pygame.Surface:
        """Return a sprite from the stack."""
        raise NotImplementedError


class SpriteFrame(SpriteStackInterface):
    """A prototype Sprite Frame class."""

    def __init__(self: Self, sprite: pygame.sprite.Sprite) -> None:
        """Initialize the Sprite Frame prototype."""
        super().__init__()
        self._image = None
        self._rect = pygame.Rect((0, 0), (0, 0))

    def image(self: Self) -> pygame.Surface:
        """Return the flattened sprite stack image."""
        return self._image

    def rect(self: Self) -> pygame.Rect:
        """Return the sprite stack pygame.Rect."""
        return self._rect


class SpriteStack(SpriteStackInterface):
    """A prototype Sprite Stack class."""

    def __init__(self: Self, sprites: list[SpriteFrame] | list[pygame.Surface]) -> Self:
        """Initialize the Sprite Stack prototype."""
        self.stack = [
            SpriteFrame(sprite) if isinstance(sprite, pygame.Surface) else sprite
            for sprite in sprites
        ]
        self.frame_index = 0

        assert self.stack, "Sprite stack cannot be empty."
        assert isinstance(self.stack, list), "Sprite stack must be a list."
        assert all(isinstance(sprite, SpriteFrame) for sprite in self.stack), (
            "Sprite stack must be a list of SpriteFrame objects."
        )
        assert len(self.stack) > 0, "Sprite stack must at least one sprite."
        assert all(sprite.get_size() == self.stack[0].get_size() for sprite in self.stack), (
            "All sprites in the stack must be the same size."
        )
        assert all(sprite.get_alpha() == self.stack[0].get_alpha() for sprite in self.stack), (
            "All sprites in the stack must have the same alpha value."
        )
        assert all(
            sprite.get_colorkey() == self.stack[0].get_colorkey() for sprite in self.stack
        ), "All sprites in the stack must have the same colorkey."

    @property
    def image(self: Self) -> pygame.Surface:
        """Returns the flattened sprite stack image."""
        return self[self.frame_index].image

    @image.setter
    def image(self: Self, new_image: pygame.Surface) -> None:
        """Set the image."""
        self[self.frame_index].image = new_image

    @property
    def rect(self: Self) -> pygame.Rect:
        """Returns the sprite stack pygame.Rect."""
        return self[self.frame_index].rect

    @rect.setter
    def rect(self: Self, new_rect: pygame.Rect) -> None:
        """Set the rect."""
        self[self.frame_index].rect = new_rect

    def __getitem__(self: Self, index: int) -> SpriteFrame:
        """Return a sprite from the stack."""
        return self.stack[index]

    # def flatten(self: Self) -> pygame.Surface:
    #     """Return a fully collapsed sprite stack."""
    #     self._image = pygame.Surface(self.stack[0].get_size(), pygame.SRCALPHA)
    #     self._image.set_alpha(self.stack[0].get_alpha())
    #     self._image.set_colorkey(self.stack[0].get_colorkey())

    #     for sprite in self.stack:
    #         self._image.blit(sprite, (0, 0))

    #     return self._image


class AnimatedSpriteInterface(SpriteStackInterface, abc.ABC):
    """A formal interface for the Sprite Animation prototype."""


class AnimatedSprite(AnimatedSpriteInterface):
    """A prototype Sprite Animation class."""

    def __init__(self: Self) -> None:
        """Initialize the Sprite Animation prototype."""
        super().__init__()
        self._frames = []

    def __getitem__(self: Self, index: int) -> SpriteFrame:
        """Return a sprite from the stack."""
        return self._frames[index]


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Sprite Stack Prototype")
    logging.getLogger("glitchygames.sprite_stack")
    logging.basicConfig(
        format="%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s",
        level=logging.DEBUG,
    )

    assert issubclass(SpriteStack, SpriteStackInterface)

    sprite_stack = SpriteStack([pygame.Surface((32, 32)) for _ in range(10)])
