import logging

import pygame
import pygame._sdl2.controller

from glitchygames.events import ControllerEvents
from glitchygames.events import ResourceManager


# Pygame has a bug where _sdl2 isn't visible in certain contexts
pygame.controller = pygame._sdl2.controller

LOG = logging.getLogger('game.controllers')
LOG.addHandler(logging.NullHandler())


class ControllerManager(ControllerEvents, ResourceManager):
    log = LOG

    class ControllerProxy(ControllerEvents, ResourceManager):
        log = LOG

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
            self.proxies = [self.game, pygame.controller]

        def on_controller_axis_motion_event(self, event):
            self.log.info(f'Controller Proxy Event: {event}')
        def on_controller_button_down_event(self, event):
            self.log.info(f'Controller Proxy Event: {event}')
        def on_controller_button_up_event(self, event):
            self.log.info(f'Controller Proxy Event: {event}')
        def on_controller_device_added_event(self, event):
            self.log.info(f'Controller Proxy Event: {event}')
        def on_controller_device_remapped_event(self, event):
            self.log.info(f'Controller Proxy Event: {event}')
        def on_controller_device_removed_event(self, event):
            self.log.info(f'Controller Proxy Event: {event}')
        def on_controller_touchpad_down_event(self, event):
            self.log.info(f'Controller Proxy Event: {event}')
        def on_controller_touchpad_motion_event(self, event):
            self.log.info(f'Controller Proxy Event: {event}')
        def on_controller_touchpad_up_event(self, event):
            self.log.info(f'Controller Proxy Event: {event}')

    def __init__(self, game=None):
        """
        Manage controllers.
        ConrollerManager manages controller events.
        Args:
        ----
        game -
        """
        super().__init__(game=game)
        self.controllers = []

        # This must be called before other joystick methods,
        # and is safe to call more than once.
        pygame.controller.init()

        self.log.info(f'Joystick Module Inited: {pygame._sdl2.controller.get_init()}')

        # Joystick Setup
        self.log.info(f'Joystick Count: {pygame._sdl2.controller.get_count()}')
        controllers = [
            pygame.controller.Controller(x)
            for x in range(pygame.controller.get_count())
        ]

        for controller in controllers:
            controller.init()
            controller_proxy = ControllerManager.ControllerProxy(
                controller_id=controller.get_id(),
                game=game
            )
            self.controllers.append(controller_proxy)

            # The joystick proxy overrides the joystick object
            log.info(controller_proxy)

        # self.proxies = [ControllerManager.ControllerProxy(game=game)]

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Controller Options')  # noqa: W0612

        return parser

    def on_controller_axis_motion_event(self, event):
        self.log.info(f'Controller Manager Event: {event}')
    def on_controller_button_down_event(self, event):
        self.log.info(f'Controller Manager Event: {event}')
    def on_controller_button_up_event(self, event):
        self.log.info(f'Controller Manager Event: {event}')
    def on_controller_device_added_event(self, event):
        self.log.info(f'Controller Manager Event: {event}')
    def on_controller_device_remapped_event(self, event):
        self.log.info(f'Controller Manager Event: {event}')
    def on_controller_device_removed_event(self, event):
        self.log.info(f'Controller Manager Event: {event}')
    def on_controller_touchpad_down_event(self, event):
        self.log.info(f'Controller Manager Event: {event}')
    def on_controller_touchpad_motion_event(self, event):
        self.log.info(f'Controller Manager Event: {event}')
    def on_controller_touchpad_up_event(self, event):
        self.log.info(f'Controller Manager Event: {event}')
