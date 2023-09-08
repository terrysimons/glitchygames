import os.path

import pygame.mixer


# Load sound files
def load_sound(snd_file: str, volume: float = 0.25) -> pygame.mixer.Sound:
    path = os.path.join(
        os.path.dirname(__file__),
        'snd_files',
        snd_file
    )
    sound = pygame.mixer.Sound(path)
    sound.set_volume(volume)
    return sound
