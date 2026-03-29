"""Glitchy Games Engine sprite module.

Re-exports all public names from submodules for backwards compatibility.
"""

from __future__ import annotations

from .animated import AnimatedSprite
from .animated_interface import AnimatedSpriteInterface
from .bitmappy_sprite import (
    BitmappySprite,
    FocusableSingletonBitmappySprite,
    Singleton,
    SingletonBitmappySprite,
)
from .constants import DEFAULT_FILE_FORMAT, SPRITE_GLYPHS
from .factory import SpriteFactory
from .frame import SpriteFrame
from .root_sprite import RootSprite
from .sprite import Sprite

__all__ = [
    'DEFAULT_FILE_FORMAT',
    'SPRITE_GLYPHS',
    'AnimatedSprite',
    'AnimatedSpriteInterface',
    'BitmappySprite',
    'FocusableSingletonBitmappySprite',
    'RootSprite',
    'Singleton',
    'SingletonBitmappySprite',
    'Sprite',
    'SpriteFactory',
    'SpriteFrame',
]
