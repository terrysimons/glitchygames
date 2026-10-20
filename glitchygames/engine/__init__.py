"""Contains GameEngine and helper classes for building a game."""

# Re-exported so games and scripts can exit with the engine's codes (glitchygames/exit_codes.py)
from glitchygames.engine.game_engine import (
    ASSET_PATH,
    DEFAULT_TARGET_FPS,
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
from glitchygames.exit_codes import ExitCode

__all__ = [
    'ASSET_PATH',
    'DEFAULT_TARGET_FPS',
    'LOG',
    'PACKAGE_PATH',
    'PYGAME_MIN_MAJOR_VERSION',
    'PYGAME_MIN_MINOR_VERSION',
    'TEST_MODE',
    'UNKNOWN_SDL2_EVENT_TYPE_1543',
    'ExitCode',
    'GameEngine',
    'GameEventManager',
]
