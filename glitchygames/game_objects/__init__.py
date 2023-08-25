import os.path

import pygame.mixer


# Load sound files
def load_sound(snd_file, volume=.25):
    path = os.path.join(
        os.path.dirname(__file__),
        'snd_files',
        snd_file
    )
    sound = pygame.mixer.Sound(path)
    sound.set_volume(volume)
    return sound
