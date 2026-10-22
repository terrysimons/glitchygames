"""Game state persistence module for GlitchyGames.

Provides a format-agnostic save/load API with pluggable serializers,
atomic writes for crash safety, and cross-platform save directory
resolution.

Usage:
    from glitchygames.state import open_saves

    saves = open_saves(app_name='my_game')  # a DiskSaveManager in live play
    saves.save('slot_1', {'score': 100, 'level': 2})
    data = saves.load('slot_1')
"""

from glitchygames.state.exceptions import (
    SaveCorruptedError,
    SaveError,
    SaveNotFoundError,
    SaveVersionError,
)
from glitchygames.state.manager import DiskSaveManager, SaveManager, SaveSlotInfo
from glitchygames.state.paths import get_save_directory
from glitchygames.state.sandbox import MemorySaveManager, open_saves, save_namespace_snapshot
from glitchygames.state.serializers import JsonSerializer, Serializer, TomlSerializer

__all__ = [
    'DiskSaveManager',
    'JsonSerializer',
    'MemorySaveManager',
    'SaveCorruptedError',
    'SaveError',
    'SaveManager',
    'SaveNotFoundError',
    'SaveSlotInfo',
    'SaveVersionError',
    'Serializer',
    'TomlSerializer',
    'get_save_directory',
    'open_saves',
    'save_namespace_snapshot',
]
