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
    def __getitem__(self: Self, index: int) -> "SpriteFrame":
        """Return a sprite from the stack."""
        raise NotImplementedError


class SpriteFrame(SpriteStackInterface):
    """A prototype Sprite Frame class."""

    def __init__(self: Self, sprite: pygame.Surface) -> None:
        """Initialize the Sprite Frame prototype."""
        super().__init__()
        self._image = sprite
        self._rect = pygame.Rect((0, 0), sprite.get_size())

    @property
    def image(self: Self) -> pygame.Surface:
        """Return the flattened sprite stack image."""
        return self._image

    @image.setter
    def image(self: Self, new_image: pygame.Surface) -> None:
        """Set the image."""
        self._image = new_image

    @property
    def rect(self: Self) -> pygame.Rect:
        """Return the sprite stack pygame.Rect."""
        return self._rect

    @rect.setter
    def rect(self: Self, new_rect: pygame.Rect) -> None:
        """Set the rect."""
        self._rect = new_rect

    def __getitem__(self: Self, index: int) -> "SpriteFrame":
        """Return a sprite from the stack."""
        return self

    def get_size(self: Self) -> tuple[int, int]:
        """Return the size of the surface."""
        return self._image.get_size()

    def get_alpha(self: Self) -> int:
        """Return the alpha value of the surface."""
        return self._image.get_alpha()

    def get_colorkey(self: Self) -> int | None:
        """Return the colorkey of the surface."""
        return self._image.get_colorkey()


class SpriteStack(SpriteStackInterface):
    """A prototype Sprite Stack class."""

    def __init__(self: Self, sprites: list["SpriteFrame"] | list[pygame.Surface]) -> Self:
        """Initialize the Sprite Stack prototype."""
        self.stack = [
            SpriteFrame(sprite) if isinstance(sprite, pygame.Surface) else sprite
            for sprite in sprites
        ]
        self.frame_index = 0

        # Validation moved to tests - allows flexible initialization

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

    def __getitem__(self: Self, index: int) -> "SpriteFrame":
        """Return a sprite from the stack."""
        return self.stack[index]


class AnimatedSpriteInterface(abc.ABC):
    """A formal interface for the Sprite Animation prototype."""

    # Animation state properties (read-only)
    @property
    @abc.abstractmethod
    def current_animation(self: Self) -> str:
        """Return the current animation name."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def current_frame(self: Self) -> int:
        """Return the current frame index."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def is_playing(self: Self) -> bool:
        """Return whether animation is currently playing."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def is_looping(self: Self) -> bool:
        """Return whether current animation loops."""
        raise NotImplementedError

    # Animation information properties
    @property
    @abc.abstractmethod
    def frames(self: Self) -> dict[str, list["SpriteFrame"]]:
        """Return all frames for all animations (including interpolated)."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def animations(self: Self) -> dict[str, dict]:
        """Return animation metadata for all animations."""
        raise NotImplementedError

    # Direct animation metadata access (current animation)
    @property
    @abc.abstractmethod
    def frame_interval(self: Self) -> float:
        """Return the frame interval for the current animation."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def loop(self: Self) -> bool:
        """Return whether the current animation loops."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def frame_count(self: Self) -> int:
        """Return the number of frames in the current animation."""
        raise NotImplementedError

    # Control properties (write-only)
    @property
    @abc.abstractmethod
    def next_animation(self: Self) -> str:
        """Get the next animation to play."""
        raise NotImplementedError

    @next_animation.setter
    @abc.abstractmethod
    def next_animation(self: Self, animation_name: str) -> None:
        """Set the next animation to play (resets frame_index to 0)."""
        raise NotImplementedError

    # Animation control methods
    @abc.abstractmethod
    def play_animation(self: Self, animation_name: str) -> None:
        """Start playing a specific animation."""
        raise NotImplementedError

    @abc.abstractmethod
    def play(self: Self) -> None:
        """Resume current animation."""
        raise NotImplementedError

    @abc.abstractmethod
    def pause(self: Self) -> None:
        """Pause current animation (preserves position)."""
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self: Self) -> None:
        """Stop animation and reset to frame 0."""
        raise NotImplementedError

    # Frame access by animation name
    @abc.abstractmethod
    def __getitem__(self: Self, animation_name: str) -> "SpriteFrame":
        """Return the current frame of the specified animation."""
        raise NotImplementedError

    # Sprite properties for drawing system
    @property
    @abc.abstractmethod
    def image(self: Self) -> pygame.Surface:
        """Return current frame's surface."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def rect(self: Self) -> pygame.Rect:
        """Return current frame's rect."""
        raise NotImplementedError


class AnimatedSprite(AnimatedSpriteInterface):
    """A prototype Sprite Animation class."""

    def __init__(self: Self, filename: str | None = None) -> None:
        """Initialize the Sprite Animation prototype."""
        super().__init__()
        self._animations = {}  # animation_name -> list of frames
        self._current_animation = ""
        self._current_frame = 0
        self._is_playing = False
        self._is_looping = False

        if filename:
            self.load(filename)

    def __getitem__(self: Self, animation_name: str) -> "SpriteFrame":
        """Return the current frame of the specified animation."""
        pass

    def get_current_frame(self: Self) -> "SpriteFrame":
        """Return the current frame as a "SpriteFrame"."""
        pass

    # Sprite properties - return current frame's surface information
    @property
    def image(self: Self) -> pygame.Surface:
        """Return current frame's surface."""
        pass

    @property
    def rect(self: Self) -> pygame.Rect:
        """Return current frame's rect."""
        pass

    # Animation state properties (read-only)
    @property
    def current_animation(self: Self) -> str:
        """Return the current animation name."""
        pass

    @property
    def current_frame(self: Self) -> int:
        """Return the current frame index."""
        pass

    @property
    def is_playing(self: Self) -> bool:
        """Return whether animation is currently playing."""
        pass

    @property
    def is_looping(self: Self) -> bool:
        """Return whether current animation loops."""
        pass

    # Animation information properties
    @property
    def frames(self: Self) -> dict[str, list["SpriteFrame"]]:
        """Return all frames for all animations (including interpolated)."""
        pass

    @property
    def animations(self: Self) -> dict[str, dict]:
        """Return animation metadata for all animations."""
        pass

    # Direct animation metadata access (current animation)
    @property
    def frame_interval(self: Self) -> float:
        """Return the frame interval for the current animation."""
        pass

    @property
    def loop(self: Self) -> bool:
        """Return whether the current animation loops."""
        pass

    @property
    def frame_count(self: Self) -> int:
        """Return the number of frames in the current animation."""
        pass

    # Control properties (write-only)
    @property
    def next_animation(self: Self) -> str:
        """Get the next animation to play."""
        pass

    @next_animation.setter
    def next_animation(self: Self, animation_name: str) -> None:
        """Set the next animation to play (resets frame_index to 0)."""
        pass

    # Animation control methods
    def play_animation(self: Self, animation_name: str) -> None:
        """Start playing a specific animation."""
        pass

    def play(self: Self) -> None:
        """Resume current animation."""
        pass

    def pause(self: Self) -> None:
        """Pause current animation (preserves position)."""
        pass

    def stop(self: Self) -> None:
        """Stop animation and reset to frame 0."""
        pass

    # Animation loading
    def load(self: Self, filename: str) -> None:
        """Load animated sprite from INI file."""
        pass

    def update(self: Self, dt: float) -> None:
        """Update animation timing."""
        pass

    def save(self: Self, filename: str, file_format: str = "ini") -> None:
        """Save animated sprite to a file."""
        # For now, raise an error since AnimatedSprite save is not implemented
        raise NotImplementedError("AnimatedSprite save functionality not yet implemented")


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Sprite Stack Prototype")
    logging.getLogger("glitchygames.sprite_stack")
    logging.basicConfig(
        format="%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s",
        level=logging.DEBUG,
    )

    assert issubclass(SpriteStack, SpriteStackInterface)

    sprite_stack = SpriteStack([pygame.Surface((32, 32)) for _ in range(10)])
