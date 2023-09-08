from __future__ import annotations

from pathlib import Path

import pygame.mixer


# Load sound files
def load_sound(snd_file: str, volume: float = 0.25) -> pygame.mixer.Sound:
    path = Path(Path.parent(__file__)) / 'snd_files' / snd_file
    sound = pygame.mixer.Sound(path)
    sound.set_volume(volume)
    return sound
