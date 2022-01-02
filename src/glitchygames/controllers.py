import logging

import pygame

from glitchygames.events import ControllerEvents
from glitchygames.events import ResourceManager


log = logging.getLogger('game.audio')
log.addHandler(logging.NullHandler())


class ControllerManager(ResourceManager):
    class ControllerProxy(ControllerEvents, ResourceManager):
        def __init__(self, game=None):
            """
            Pygame controller event proxy.

            ControllerProxy facilitates mouse handling by bridging CONTROLLER* events between
            pygame and your game.

            Args:
            ----
            game - The game instance.

            """
            super().__init__(game)

            self.game = game
            # self.proxies = [self.game, pygame._sdl2.controller]

    def __init__(self, game=None):
        """
        Manage controllers.

        ConrollerManager manages controller events.

        Args:
        ----
        game -

        """
        super().__init__(game=game)

        self.proxies = [ControllerManager.ControllerProxy(game=game)]

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Controller Options')  # noqa: W0612

        return parser
