import logging

import pygame

from ghettogames.events import KeyboardEvents
from ghettogames.events import ResourceManager


log = logging.getLogger('game.keyboard')
log.addHandler(logging.NullHandler())


class KeyboardManager(ResourceManager):
    class KeyboardProxy(KeyboardEvents, ResourceManager):
        def __init__(self, game=None):
            """
            Pygame keyboard event proxy.

            KeyboardProxy facilitates key handling by bridging keyboard events between
            pygame and your game.

            Args:
            ----
            game - The game instance.

            """
            super().__init__(game=game)
            self.keys = {}
            self.game = game
            self.proxies = [self.game, pygame.key]

        def on_key_down_event(self, event):
            # The KEYUP and KEYDOWN events are
            # different.  KEYDOWN contains an extra
            # key in its dictionary (unicode), which
            # KEYUP does not contain, so we'll make
            # a copy of the dictionary, and then
            # delete the key "unicode" so we can track
            # both sets of events.
            keyboard_key = event.dict.copy()
            del keyboard_key['unicode']

            # This makes it possible to use
            # a dictionary as a key, which is
            # normally not possible.
            self.keys[
                tuple(
                    sorted(
                        frozenset(keyboard_key.items())
                    )
                )
            ] = event

            self.game.on_key_down_event(event)
            self.on_key_chord_down_event(event)

        def on_key_up_event(self, event):
            # This makes it possible to use
            # a dictionary as a key, which is
            # normally not possible.
            self.keys[
                tuple(
                    sorted(
                        frozenset(event.dict.items())
                    )
                )
            ] = event

            self.game.on_key_up_event(event)
            self.on_key_chord_up_event(event)

        def on_key_chord_down_event(self, event):
            keys_down = [self.keys[key]
                         for key in self.keys
                         if self.keys[key].type == pygame.KEYDOWN]

            self.game.on_key_chord_down_event(event, keys_down)

        def on_key_chord_up_event(self, event):
            keys_down = [self.keys[key]
                         for key in self.keys
                         if self.keys[key].type == pygame.KEYDOWN]

            self.game.on_key_chord_up_event(event, keys_down)

    def __init__(self, game=None):
        """
        Keyboard event manager.

        KeyboardManager interfaces GameEngine with KeyboardManager.KeyboardManagerProxy.

        Args:
        ----
        game - The game instance.

        """
        super().__init__(game=game)
        self.proxies = [KeyboardManager.KeyboardProxy(game=game)]