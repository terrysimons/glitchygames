#!/usr/bin/env python3
"""Audio.

This is a simple audio manager that can be used to manage audio.
"""

import argparse
import logging
from typing import Self

import pygame
from glitchygames.events import AUDIO_EVENTS
from glitchygames.events import AudioEvents, ResourceManager

log = logging.getLogger("game.audio")
log.addHandler(logging.NullHandler())


class AudioEventManager(ResourceManager):
    """Manage pygame audio events."""

    class AudioEventProxy(AudioEvents, ResourceManager):
        """Pygame audio event proxy."""

        def __init__(self: Self, game: object = None) -> None:
            """Initialize the audio proxy.

            Args:
                game: The game instance.

            Returns:
                None

            """
            super().__init__(game)

            self.game = game
            self.proxies = [self.game, pygame.mixer]

        def on_audio_device_added_event(self: Self, event: pygame.event.Event) -> None:
            """Handle audio device added event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            self.game.on_audio_device_added_event(event)

        def on_audio_device_removed_event(self: Self, event: pygame.event.Event) -> None:
            """Handle audio device removed event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            self.game.on_audio_device_removed_event(event)

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the audio manager.

        Args:
            game: The game instance.

        Returns:
            None

        """
        super().__init__(game=game)
        try:
            pygame.event.set_allowed(AUDIO_EVENTS)
        except Exception:
            pass

        # Set the mixer pre-init settings
        pygame.mixer.pre_init(22050, -16, 2, 1024)
        pygame.mixer.init()

        # Sound Stuff
        # pygame.mixer.get_init() -> (frequency, format, channels)
        (sound_frequency, sound_format, sound_channels) = pygame.mixer.get_init()
        log.info("Mixer Settings:")
        log.info(
            f"Frequency: {sound_frequency}, Format: {sound_format}, Channels: {sound_channels}"
        )

        self.proxies = [AudioEventManager.AudioEventProxy(game=game)]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add arguments to the argument parser.

        Args:
            parser: The argument parser.

        Returns:
            The argument parser.

        """
        group: argparse._ArgumentGroup = parser.add_argument_group(  # noqa: F841
            "Sound Mixer Options"
        )

        return parser
