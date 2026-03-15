"""Contains GameEngine and helper classes for building a game."""

from glitchygames.engine.game_engine import (
    ASSET_PATH,
    LOG,
    PACKAGE_PATH,
    PYGAME_MIN_MAJOR_VERSION,
    PYGAME_MIN_MINOR_VERSION,
    TEST_MODE,
    UNKNOWN_SDL2_EVENT_TYPE_1543,
    GameEngine,
)

# Re-export GameEventManager since it was importable from glitchygames.engine
from glitchygames.events.game import GameEventManager

__all__ = [
    'ASSET_PATH',
    'LOG',
    'PACKAGE_PATH',
    'PYGAME_MIN_MAJOR_VERSION',
    'PYGAME_MIN_MINOR_VERSION',
    'TEST_MODE',
    'UNKNOWN_SDL2_EVENT_TYPE_1543',
    'GameEngine',
    'GameEventManager',
]
