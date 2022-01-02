import logging

import pygame

from glitchygames.events import JoystickEvents
from glitchygames.events import ResourceManager


log = logging.getLogger('game.joysticks')
log.addHandler(logging.NullHandler())


class JoystickManager(ResourceManager):
    # Interiting from object is default in Python 3.
    # Linters complain if you do it.
    #
    # This isn't a ResourceManager like other proxies, because
    # there can be multiple joysticks, so having one instance
    # won't work.
    class JoystickProxy(JoystickEvents):
        def __init__(self, game=None, joystick_id=-1):
            """
            Pygame joystick event proxy.

            JoystickProxy facilitates joystick handling by bridging joystick events between
            pygame and your game.

            Args:
            ----
            joystick_id - the id of the joystick to init
            game - The game instance.

            """
            super().__init__()
            self._id = joystick_id
            self.joystick = pygame.joystick.Joystick(self._id)
            self.joystick.init()
            self._name = self.joystick.get_name()
            self._init = self.joystick.get_init()

            self._numaxes = self.joystick.get_numaxes()
            self._numballs = self.joystick.get_numballs()
            self._numbuttons = self.joystick.get_numbuttons()
            self._numhats = self.joystick.get_numhats()

            # Initialize button state.
            self._axes = [self.joystick.get_axis(i)
                          for i in range(self.get_numaxes())]

            self._balls = [self.joystick.get_ball(i)
                           for i in range(self.get_numballs())]

            self._buttons = [self.joystick.get_button(i)
                             for i in range(self.get_numbuttons())]

            self._hats = [self.joystick.get_hat(i)
                          for i in range(self.get_numhats())]

            self.game = game
            self.proxies = [self.game, self.joystick]

        # Define some high level APIs
        def on_axis_motion_event(self, event):
            # JOYAXISMOTION    joy, axis, value
            self._axes[event.axis] = event.value
            self.game.on_axis_motion_event(event)

        def on_button_down_event(self, event):
            # JOYBUTTONDOWN    joy, button
            self._buttons[event.button] = 1
            self.game.on_button_down_event(event)

        def on_button_up_event(self, event):
            # JOYBUTTONUP      joy, button
            self._buttons[event.button] = 0
            self.game.on_button_up_event(event)

        def on_hat_motion_event(self, event):
            # JOYHATMOTION     joy, hat, value
            self._hats[event.hat] = event.value
            self.game.on_hat_motion_event(event)

        def on_ball_motion_event(self, event):
            # JOYBALLMOTION    joy, ball, rel
            self._balls[event.ball] = event.rel
            self.game.on_ball_motion_event(event)

        # We can't make these properties, because then they
        # wouldn't be callable as functions.
        def get_name(self):
            return self._name

        def get_init(self):
            return self._init

        def get_numaxes(self):
            return self._numaxes

        def get_numballs(self):
            return self._numballs

        def get_numbuttons(self):
            return self._numbuttons

        def get_numhats(self):
            return self._numhats

        def __str__(self):
            joystick_info = []
            joystick_info.append(f'Joystick Name: {self.get_name()}')
            joystick_info.append(f'\tJoystick Id: {self._id}')
            joystick_info.append(f'\tJoystick Inited: {self.get_init()}')
            joystick_info.append(f'\tJoystick Axis Count: {self.get_numaxes()}')
            joystick_info.append(f'\tJoystick Trackball Count: {self.get_numballs()}')
            joystick_info.append(f'\tJoystick Button Count: {self.get_numbuttons()}')
            joystick_info.append(f'\tJoystick Hat Count: {self.get_numhats()}')
            return '\n'.join(joystick_info)

        def __repr__(self):
            return repr(self.joystick)

    def __init__(self, game=None):
        """
        Joystick event manager.

        JoystickManager interfaces GameEngine with JoystickManager.JoystickProxy.

        Args:
        ----
        game - The game instance.

        """
        super().__init__(game=game)
        self.joysticks = []

        # This must be called before other joystick methods,
        # and is safe to call more than once.
        pygame.joystick.init()

        log.info(f'Joystick Module Inited: {pygame.joystick.get_init()}')

        # Joystick Setup
        log.info(f'Joystick Count: {pygame.joystick.get_count()}')
        joysticks = [pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())]

        for joystick in joysticks:
            joystick.init()
            joystick_proxy = JoystickManager.JoystickProxy(
                joystick_id=joystick.get_id(),
                game=game
            )
            self.joysticks.append(joystick_proxy)

            # The joystick proxy overrides the joystick object
            log.info(joystick_proxy)

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Joystick Options')  # noqa: W0612

        return parser

    # Define some high level APIs
    #
    # Note that we can't pass these through the way
    # we do for other event types because
    # we need to know which joystick the event is intended for.
    def on_axis_motion_event(self, event):
        # JOYAXISMOTION    joy, axis, value
        log.debug(f'JOYAXISMOTION triggered: axis_motion_event({event})')
        self.joysticks[event.joy].on_axis_motion_event(event)

    def on_button_down_event(self, event):
        # JOYBUTTONDOWN    joy, button
        log.debug(f'JOYBUTTONDOWN triggered: button_down_event({event})')
        self.joysticks[event.joy].on_button_down_event(event)

    def on_button_up_event(self, event):
        # JOYBUTTONUP      joy, button
        log.debug(f'JOYBUTTONUP triggered: button_up_event({event})')
        self.joysticks[event.joy].on_button_up_event(event)

    def on_hat_motion_event(self, event):
        # JOYHATMOTION     joy, hat, value
        log.debug(f'JOYHATMOTION triggered: hat_motion_event({event})')
        self.joysticks[event.joy].on_hat_motion_event(event)

    def on_ball_motion_event(self, event):
        # JOYBALLMOTION    joy, ball, rel
        log.debug(f'JOYBALLMOTION triggered: ball_motion_event({event})')
        self.joysticks[event.joy].on_ball_motion_event(event)
