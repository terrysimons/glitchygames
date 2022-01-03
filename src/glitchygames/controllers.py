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

        AXIS = [
            pygame.CONTROLLER_AXIS_LEFTX,
            pygame.CONTROLLER_AXIS_LEFTY,
            pygame.CONTROLLER_AXIS_RIGHTX,
            pygame.CONTROLLER_AXIS_RIGHTY,
            pygame.CONTROLLER_AXIS_TRIGGERLEFT,
            pygame.CONTROLLER_AXIS_TRIGGERRIGHT
        ]

        BUTTONS = [
            pygame.CONTROLLER_BUTTON_A,
            pygame.CONTROLLER_BUTTON_B,
            pygame.CONTROLLER_BUTTON_X,
            pygame.CONTROLLER_BUTTON_Y,
            pygame.CONTROLLER_BUTTON_DPAD_UP,
            pygame.CONTROLLER_BUTTON_DPAD_DOWN,
            pygame.CONTROLLER_BUTTON_DPAD_LEFT,
            pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
            pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
            pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
            pygame.CONTROLLER_BUTTON_LEFTSTICK,
            pygame.CONTROLLER_BUTTON_RIGHTSTICK,
            pygame.CONTROLLER_BUTTON_BACK,
            pygame.CONTROLLER_BUTTON_GUIDE,
            pygame.CONTROLLER_BUTTON_START
        ]

        def __init__(self, game=None, controller_id=-1):
            """
            Pygame controller event proxy.
            ControllerProxy facilitates mouse handling by bridging CONTROLLER* events between
            pygame and your game.
            Args:
            ----
            game - The game instance.
            """
            super().__init__(game)

            self._id = controller_id
            self.controller = pygame._sdl2.controller.Controller(self._id)
            self.controller.init()
            self._name = pygame._sdl2.controller.name_forindex(self._id)
            self._init = self.controller.get_init()
            self._attached = self.controller.attached()

            self._numaxes = len(self.AXIS)
            self._numbuttons = len(self.BUTTONS)
            self._mapping = self.controller.get_mapping()

            # Initialize button state.
            self._axes = [self.controller.get_axis(i)
                          for i in range(self._numaxes)]

            self._buttons = [self.controller.get_button(i)
                             for i in range(self._numbuttons)]

            self.game = game
            self.proxies = [self.game, self.controller]

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

        def __str__(self):
            joystick_info = []
            joystick_info.append(f'Controller Name: {pygame._sdl2.controller.name_forindex(self._id)}')
            joystick_info.append(f'\tController Id: {self._id}')
            joystick_info.append(f'\tController Inited: {self.controller.get_init()}')
            joystick_info.append(f'\tController Axis Count: {self._numaxes}')
            joystick_info.append(f'\tController Button Count: {self._numbuttons}')
            return '\n'.join(joystick_info)

        def __repr__(self):
            return repr(self.joystick)

    def __init__(self, game=None):
        """
        Manage controllers.
        ConrollerManager manages controller events.
        Args:
        ----
        game -
        """
        super().__init__(game=game)
        self.controllers = {}
        self.proxies = []

        # This must be called before other joystick methods,
        # and is safe to call more than once.
        pygame._sdl2.controller.init()

        self.log.info(f'Controller Module Inited: {pygame._sdl2.controller.get_init()}')

        # Controller Setup
        self.log.info(f'Controller Count: {pygame._sdl2.controller.get_count()}')

        if pygame._sdl2.controller.get_count():
            controllers = [
                pygame._sdl2.controller.Controller(x)
                for x in range(pygame._sdl2.controller.get_count())
            ]

            for controller in controllers:
                controller.init()
                controller_proxy = ControllerManager.ControllerProxy(
                    controller_id=controller.get_id(),
                    game=game
                )
                self.controllers.append(controller_proxy)

                # The controller proxy overrides the joystick object
                self.log.info(controller_proxy)

            # self.proxies = [ControllerManager.ControllerProxy(game=game), pygame.controller]

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
        self.log.info(f'Controller Count: {pygame._sdl2.controller.get_count()}')
        controllers = [pygame._sdl2.controller.Controller(x) for x in range(pygame._sdl2.controller.get_count())]

        for controller in controllers:
            controller.init()

            controller_proxy = ControllerManager.ControllerProxy(
                controller_id=controller.id,
                game=self.game
            )
            self.controllers[controller.id] = controller_proxy

            # The controller proxy overrides the joystick object
            self.log.info(f'Added Controller: {controller_proxy}')

        self.log.info(f'CONTROLLERADDED triggered: on_controller_device_added({event})')
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
