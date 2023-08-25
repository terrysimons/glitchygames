import logging

import pygame

from glitchygames.events import JoystickEvents, ResourceManager

LOG = logging.getLogger('game.joysticks')
LOG.addHandler(logging.NullHandler())


class JoystickManager(JoystickEvents, ResourceManager):
    log = LOG
    # Interiting from object is default in Python 3.
    # Linters complain if you do it.
    #
    # This isn't a ResourceManager like other proxies, because
    # there can be multiple joysticks, so having one instance
    # won't work.

    class JoystickProxy(JoystickEvents, ResourceManager):
        log = LOG

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
            super().__init__(game=game)
            self._id = joystick_id
            self.joystick = pygame.joystick.Joystick(self._id)
            self.joystick.init()
            self._init = self.joystick.get_init()
            self._name = self.joystick.get_name()

            try:
                self._guid = self.joystick.get_guid()
            except AttributeError:
                self._guid = None

            try:
                self._power_level = self.joystick.get_power_level()
            except AttributeError:
                self._power_level = None

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
        def on_joy_axis_motion_event(self, event):
            # JOYAXISMOTION    joy, axis, value
            self._axes[event.axis] = event.value
            self.game.on_joy_axis_motion_event(event)

        def on_joy_button_down_event(self, event):
            # JOYBUTTONDOWN    joy, button
            self._buttons[event.button] = 1
            self.game.on_joy_button_down_event(event)

        def on_joy_button_up_event(self, event):
            # JOYBUTTONUP      joy, button
            self._buttons[event.button] = 0
            self.game.on_joy_button_up_event(event)

        def on_joy_hat_motion_event(self, event):
            # JOYHATMOTION     joy, hat, value
            self._hats[event.hat] = event.value
            self.game.on_joy_hat_motion_event(event)

        def on_joy_ball_motion_event(self, event):
            # JOYBALLMOTION    joy, ball, rel
            self._balls[event.ball] = event.rel
            self.game.on_joy_ball_motion_event(event)

        def on_joy_device_added_event(self, event):
            # JOYDEVICEADDED device_index, guid
            self.game.on_joy_device_added_event(event)

        def on_joy_device_removed_event(self, event):
            # JOYDEVICEREMOVED device_index
            self.game.on_joy_device_removed_event(event)

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
        self.joysticks = {}
        self.game = game

        # This must be called before other joystick methods,
        # and is safe to call more than once.
        pygame.joystick.init()

        self.log.info(f'Joystick Module Inited: {pygame.joystick.get_init()}')

        # Joystick Setup
        self.log.info(f'Joystick Count: {pygame.joystick.get_count()}')
        joysticks = [pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())]

        for joystick in joysticks:
            joystick.init()

            try:
                joystick_id = joystick.get_instance_id()
            except AttributeError:
                joystick_id = joystick.get_id()

            joystick_proxy = JoystickManager.JoystickProxy(
                joystick_id=joystick_id,
                game=self.game
            )
            self.joysticks[joystick_id] = joystick_proxy

            # The joystick proxy overrides the joystick object
            self.log.info(f'Added Joystick: {joystick_proxy}')

        self.proxies = [self.game]

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Joystick Options')  # noqa: W0612, F841

        return parser

    # Define some high level APIs
    #
    # Note that we can't pass these through the way
    # we do for other event types because
    # we need to know which joystick the event is intended for.
    def on_joy_axis_motion_event(self, event):
        # JOYAXISMOTION    joy, axis, value
        try:
            id = event.instance_id
        except AttributeError:
            id = event.joy

        self.log.debug(f'JOYAXISMOTION triggered: on_joy_axis_motion_event({event})')
        self.joysticks[id].on_joy_axis_motion_event(event)

    def on_joy_button_down_event(self, event):
        # JOYBUTTONDOWN    joy, button
        try:
            id = event.instance_id
        except AttributeError:
            id = event.joy

        self.log.debug(f'JOYBUTTONDOWN triggered: on_joy_button_down_event({event})')
        self.joysticks[id].on_joy_button_down_event(event)

    def on_joy_button_up_event(self, event):
        # JOYBUTTONUP      joy, button
        try:
            id = event.instance_id
        except AttributeError:
            id = event.joy

        self.log.debug(f'JOYBUTTONUP triggered: on_joy_button_up_event({event})')
        self.joysticks[id].on_joy_button_up_event(event)

    def on_joy_hat_motion_event(self, event):
        # JOYHATMOTION     joy, hat, value
        try:
            id = event.instance_id
        except AttributeError:
            id = event.joy

        self.log.debug(f'JOYHATMOTION triggered: on_joy_hat_motion_event({event})')
        self.joysticks[id].on_joy_hat_motion_event(event)

    def on_joy_ball_motion_event(self, event):
        # JOYBALLMOTION    joy, ball, rel
        try:
            id = event.instance_id
        except AttributeError:
            id = event.joy

        self.log.debug(f'JOYBALLMOTION triggered: on_joy_ball_motion_event({event})')
        self.joysticks[id].on_joy_ball_motion_event(event)

    def on_joy_device_added_event(self, event):
        # JOYDEVICEADDED device_index, guid

        # Note: There is a bug in pygame where a reinitialized
        # controller object due to hotplug ends up with an incorrect
        # device_index.
        joystick_proxy = JoystickManager.JoystickProxy(
            joystick_id=event.device_index,
            game=self.game
        )
        self.joysticks[event.device_index] = joystick_proxy

        # The joystick proxy overrides the joystick object
        self.log.debug(f'Added Joystick #{event.device_index}: {joystick_proxy}')
        self.log.debug(f'JOYDEVICEADDED triggered: on_joy_device_added({event})')

        # Need to notify the game after the joystick exists
        self.joysticks[event.device_index].on_joy_device_added_event(event)

    def on_joy_device_removed_event(self, event):
        # JOYDEVICEREMOVED instance_id
        self.log.debug(f'Removed Joystick #{event.instance_id}')
        self.log.debug(f'JOYDEVICEREMOVED triggered: on_joy_device_removed({event})')

        # Need to notify the game first.
        self.joysticks[event.instance_id].on_joy_device_removed_event(event)
        del self.joysticks[event.instance_id]
