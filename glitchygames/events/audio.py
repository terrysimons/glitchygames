#!/usr/bin/env python3
"""Audio.

This is a simple audio manager that can be used to manage audio.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self, override

if TYPE_CHECKING:
    import argparse

import pygame

from glitchygames.events import AUDIO_EVENTS, AudioEvents, HashableEvent, ResourceManager

log = logging.getLogger('game.audio')
log.addHandler(logging.NullHandler())


class AudioEventManager(ResourceManager):
    """Manage pygame audio events."""

    class AudioEventProxy(AudioEvents, ResourceManager):
        """Pygame audio event proxy."""

        def __init__(self: Self, game: object = None) -> None:
            """Initialize the audio proxy.

            Args:
                game: The game instance.

            """
            super().__init__(game)

            self.game: Any = game
            self.proxies = [self.game, pygame.mixer]

        @override
        def on_audio_device_added_event(self: Self, event: HashableEvent) -> None:
            """Handle audio device added event.

            Args:
                event: The pygame event.

            """
            self.game.on_audio_device_added_event(event)

        @override
        def on_audio_device_removed_event(self: Self, event: HashableEvent) -> None:
            """Handle audio device removed event.

            Args:
                event: The pygame event.

            """
            self.game.on_audio_device_removed_event(event)

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the audio manager.

        Args:
            game: The game instance.

        """
        super().__init__(game=game)
        try:
            pygame.event.set_allowed(AUDIO_EVENTS)
        except pygame.error:
            log.debug('Failed to set allowed audio events: pygame not fully initialized')

        # Set the mixer pre-init settings
        pygame.mixer.pre_init(22050, -16, 2, 1024)
        pygame.mixer.init()

        # Sound Stuff
        # pygame.mixer.get_init() -> (frequency, format, channels)
        (sound_frequency, sound_format, sound_channels) = pygame.mixer.get_init()
        log.info('Mixer Settings:')
        log.info(
            f'Frequency: {sound_frequency}, Format: {sound_format}, Channels: {sound_channels}'
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
        _group = parser.add_argument_group('Sound Mixer Options')

        return parser
