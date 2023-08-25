import logging

import pygame

from glitchygames.events import AudioEvents, ResourceManager

log = logging.getLogger('game.audio')
log.addHandler(logging.NullHandler())


class AudioManager(ResourceManager):
    class AudioProxy(AudioEvents, ResourceManager):
        def __init__(self, game=None):
            """
            Pygame audio event proxy.

            AudioProxy facilitates mouse handling by bridging AUDIO* events between
            pygame and your game.

            Args:
            ----
            game - The game instance.

            """
            super().__init__(game)

            self.game = game
            self.proxies = [self.game, pygame.mixer]

        def on_audio_device_added_event(self, event):
            self.game.on_audio_device_added_event(event)

        def on_audio_device_removed_event(self, event):
            self.game.on_audio_device_removed_event(event)

    def __init__(self, game=None):
        """
        Manage audio.

        AudioManager manages audio.

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

        self.proxies = [AudioManager.AudioProxy(game=game)]

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Sound Mixer Options')  # noqa: W0612, F841

        return parser
