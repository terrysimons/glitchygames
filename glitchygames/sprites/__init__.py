"""Glitchy Games Engine sprite module.

Re-exports all public names from submodules for backwards compatibility.
"""

from __future__ import annotations

from .animated import AnimatedSprite, AnimatedSpriteInterface, SpriteFrame
from .constants import DEFAULT_FILE_FORMAT, SPRITE_GLYPHS
from .core import (
    BitmappySprite,
    FocusableSingletonBitmappySprite,
    RootSprite,
    Singleton,
    SingletonBitmappySprite,
    Sprite,
    SpriteFactory,
)

__all__ = [
    "DEFAULT_FILE_FORMAT",
    "SPRITE_GLYPHS",
    "AnimatedSprite",
    "AnimatedSpriteInterface",
    "BitmappySprite",
    "FocusableSingletonBitmappySprite",
    "RootSprite",
    "Singleton",
    "SingletonBitmappySprite",
    "Sprite",
    "SpriteFactory",
    "SpriteFrame",
]
