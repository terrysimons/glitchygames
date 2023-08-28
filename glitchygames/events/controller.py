#!/usr/bin/env python3
import logging
from typing import ClassVar

import pygame
import pygame._sdl2.controller  # noqa: SLF001

from glitchygames.events import ControllerEvents, ResourceManager

# Pygame has a bug where _sdl2 isn't visible in certain contexts
pygame.controller = pygame._sdl2.controller  # noqa: SLF001

LOG = logging.getLogger('game.controllers')
LOG.addHandler(logging.NullHandler())


class ControllerManager(ControllerEvents, ResourceManager):
    log = LOG

    class ControllerProxy(ControllerEvents, ResourceManager):
        log = LOG

        AXIS: ClassVar = [
            pygame.CONTROLLER_AXIS_LEFTX,
            pygame.CONTROLLER_AXIS_LEFTY,
            pygame.CONTROLLER_AXIS_RIGHTX,
            pygame.CONTROLLER_AXIS_RIGHTY,
            pygame.CONTROLLER_AXIS_TRIGGERLEFT,
            pygame.CONTROLLER_AXIS_TRIGGERRIGHT
        ]

        BUTTONS: ClassVar = [
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
            self.controller = pygame._sdl2.controller.Controller(self._id)  # noqa: SLF001
            self.controller.init()
            self._name = pygame._sdl2.controller.name_forindex(self._id)  # noqa: SLF001
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
            self._axes[event.axis] = event.value
            self.game.on_controller_axis_motion_event(event)

        def on_controller_button_down_event(self, event):
            self._buttons[event.button] = 1
            self.game.on_controller_button_down_event(event)

        def on_controller_button_up_event(self, event):
            self._buttons[event.button] = 0
            self.game.on_controller_button_up_event(event)

        def on_controller_device_added_event(self, event):
            # CONTROLLERDEVICEADDED device_index, guid
            self.game.on_controller_device_added_event(event)

        def on_controller_device_remapped_event(self, event):
            self.game.on_controller_device_remapped_event(event)

        def on_controller_device_removed_event(self, event):
            # CONTROLLERDEVICEREMOVED instance_id
            self.game.on_controller_device_removed_event(event)

        def on_controller_touchpad_down_event(self, event):
            self.game.on_controller_touchpad_down_event(event)

        def on_controller_touchpad_motion_event(self, event):
            self.game.on_controller_touchpad_motion_event(event)

        def on_controller_touchpad_up_event(self, event):
            self.game.on_controller_touchpad_up_event(event)

        def __str__(self):
            controller_info = []
            controller_info.append('Controller Name: '
                f'{pygame._sdl2.controller.name_forindex(self._id)}'  # noqa: SLF001
            )
            controller_info.append(f'\tController Id: {self._id}')
            controller_info.append(f'\tController Inited: {self.controller.get_init()}')
            controller_info.append(f'\tController Axis Count: {self._numaxes}')
            controller_info.append(f'\tController Button Count: {self._numbuttons}')
            return '\n'.join(controller_info)

        def __repr__(self):
            return repr(self.controller)

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
        self.game = game

        # This must be called before other controller methods,
        # and is safe to call more than once.
        pygame._sdl2.controller.init()  # noqa: SLF001

        self.log.debug(
            f'Controller Module Inited: {pygame._sdl2.controller.get_init()}'  # noqa: SLF001
        )

        # Controller Setup
        self.log.debug(f'Controller Count: {pygame._sdl2.controller.get_count()}')  # noqa: SLF001

        if pygame._sdl2.controller.get_count():  # noqa: SLF001
            controllers = [
                pygame._sdl2.controller.Controller(x)  # noqa: SLF001
                for x in range(pygame._sdl2.controller.get_count())  # noqa: SLF001
            ]

            for controller in controllers:
                controller.init()
                controller_proxy = ControllerManager.ControllerProxy(
                    controller_id=controller.get_id(),
                    game=game
                )
                self.controllers.append(controller_proxy)

                # The controller proxy overrides the controller object
                self.log.debug(controller_proxy)

        self.proxies = [self.game]

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Controller Options')  # noqa: W0612, F841

        return parser

    def on_controller_axis_motion_event(self, event):
        self.log.debug('CONTROLLERAXISMOTION triggered: '
                       f'on_controller_axis_motion_event({event})')
        self.controllers[event.instance_id].on_controller_axis_motion_event(event)

    def on_controller_button_down_event(self, event):
        self.log.debug('CONTROLLERBUTTONDOWNEVENT triggered: '
                       f'on_controller_button_down_event({event})')
        self.controllers[event.instance_id].on_controller_button_down_event(event)

    def on_controller_button_up_event(self, event):
        self.log.debug('CONTROLLERBUTTONUPEVENT triggered: '
                       f'on_controller_button_up_event({event})')
        self.controllers[event.instance_id].on_controller_button_up_event(event)

    def on_controller_device_added_event(self, event):
        # CONTROLLERDEVICEADDED device_index, guid

        # Note: There is a bug in pygame where a reinitialized
        # controller object due to hotplug ends up with an incorrect
        # device_index.
        controller_proxy = ControllerManager.ControllerProxy(
            controller_id=event.device_index,
            game=self.game
        )
        self.controllers[event.device_index] = controller_proxy

        # The controller proxy overrides the controller object
        self.log.debug(f'Added Controller #{event.device_index}: {controller_proxy}')
        self.log.debug('CONTROLLERDEVICEADDED triggered: '
                       f'on_controller_device_added_event({event})')

        # Need to notify the game after the controller exists
        self.controllers[event.device_index].on_controller_device_added_event(event)

    def on_controller_device_remapped_event(self, event):
        self.log.debug('CONTROLLERDEVICEREMAPPED triggered: '
                       f'on_controller_device_remapped_event({event}')
        self.controllers[event.device_index].on_controller_device_remapped_event(event)

    def on_controller_device_removed_event(self, event):
        # CONTROLLERDEVICEREMOVED instance_id
        self.controllers[event.instance_id].on_controller_device_removed_event(event)
        del self.controllers[event.instance_id]
        self.log.debug(f'Removed Controller #{event.instance_id}')
        self.log.debug('CONTROLLERDEVICEREMOVED triggered: '
                       f'on_controller_device_removed({event})')

    def on_controller_touchpad_down_event(self, event):
        self.log.debug('CONTROLLERTOUCHDPADDOWN triggered: '
                       f'on_controller_touchpad_down_event({event})')
        self.controllers[event.instance_id].on_controller_touchpad_down_event(event)

    def on_controller_touchpad_motion_event(self, event):
        self.log.debug('CONTROLLERTOUCHPADMOTION triggered: '
                       f'on_controller_touchpad_motion_event({event})')
        self.controllers[event.instance_id].on_controller_touchpad_motion_event(event)

    def on_controller_touchpad_up_event(self, event):
        self.log.debug('CONTROLLERTOUCHPADUP triggered: '
                       f'on_controller_touchpad_up_event({event})')
        self.controllers[event.instance_id].on_controller_touchpad_up_event(event)
