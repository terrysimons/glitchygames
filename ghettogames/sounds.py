import logging

import pygame

from ghettogames.events import ResourceManager


log = logging.getLogger('game.sounds')
log.addHandler(logging.NullHandler())


class SoundManager(ResourceManager):
    def __init__(self, game=None):
        """
        Manage sounds.

        SoundManager manages sounds.

        Args:
        ----
        game -

        """
        super().__init__(game=game)

        # Set the mixer pre-init settings
        pygame.mixer.pre_init(22050, -16, 2, 1024)
        pygame.mixer.init()

        # Sound Stuff
        # pygame.mixer.get_init() -> (frequency, format, channels)
        (sound_frequency, sound_format, sound_channels) = pygame.mixer.get_init()
        log.info('Mixer Settings:')
        log.info(
            f'Frequency: {sound_frequency}, '
            f'Format: {sound_format}, '
            f'Channels: {sound_channels}'
        )

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Sound Mixer Options')  # noqa: W0612

        return parser