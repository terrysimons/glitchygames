# ruff: noqa: D104
from __future__ import annotations

from pathlib import Path

import pygame.mixer


# Load sound files
def load_sound(snd_file: str, volume: float = 0.25) -> pygame.mixer.Sound:
    """Load a sound file.

    Args:
        snd_file (str): The sound file to load.
        volume (float): The volume to set the sound to.

    Returns:
        pygame.mixer.Sound: The sound object.
    """
    path: Path = Path(__file__).parent / 'snd_files' / snd_file
    sound = pygame.mixer.Sound(path)
    sound.set_volume(volume)
    return sound
