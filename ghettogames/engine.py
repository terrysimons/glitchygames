#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Contains GameEngine and helper classes for building a game."""
import abc
import collections
import configparser
import inspect
import logging
import multiprocessing
import platform
import re

import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

from ghettogames.color import PURPLE, BLACK, VGA
from ghettogames.events import ResourceManager, EventManager
from ghettogames.events import FontEvents
from ghettogames.events import KeyboardEvents, MouseEvents, JoystickEvents

log = logging.getLogger('game.engine')
log.addHandler(logging.NullHandler())

vga_palette = VGA


def indexed_rgb_triplet_generator(pixel_data):
    """Yield (R, G, B) pixel tuples from a buffer of pixel tuples."""
    try:
        for datum in pixel_data:
            yield datum[0]
    except StopIteration:
        pass


def rgb_555_triplet_generator(pixel_data):
    """Yield (R, G, B) pixel tuples for 555 formated color data."""
    try:
        # Construct RGB triplets.
        for packed_rgb_triplet in pixel_data:
            # struct unpacks as a 1 element tuple.
            rgb_data = bin(packed_rgb_triplet[0])

            # binary conversions start with 0b, so chop that off.
            rgb_data = rgb_data[2:]

            # Pad the data out.
            pad_bits = 16 - len(rgb_data)
            pad_data = '0' * pad_bits

            rgb_data = pad_data + rgb_data

            log.info(f'Padded {pad_bits} bits (now {rgb_data})')

            # red is 5 bits
            red = int(rgb_data[0:5] + '000', 2)

            if red:
                red += 7

            # green is 6 bits
            green = int(rgb_data[5:10] + '000', 2)

            if green:
                green += 7

            # blue is 5 bits
            blue = int(rgb_data[10:15] + '000', 2)

            # last bit is ignored or used for alpha.

            if blue:
                blue += 7

            log.info(f'Packed RGB: {rgb_data}')
            log.info(f'Red: {red}')
            log.info(f'Green: {green}')
            log.info(f'Blue: {blue}')

            yield tuple([red, green, blue])
    except StopIteration:
        pass


def rgb_565_triplet_generator(pixel_data):
    """Yield (R, G, B) tuples for 565 formatted color data."""
    try:
        # Construct RGB triplets.
        for packed_rgb_triplet in pixel_data:
            # struct unpacks as a 1 element tuple.
            rgb_data = bin(packed_rgb_triplet[0])

            # binary conversions start with 0b, so chop that off.
            rgb_data = rgb_data[2:]

            # Pad the data out.
            pad_bits = 16 - len(rgb_data)
            pad_data = '0' * pad_bits

            rgb_data = pad_data + rgb_data

            log.info(f'Padded {pad_bits} bits (now {rgb_data})')

            # red is 5 bits
            red = int(rgb_data[0:5] + '000', 2)

            if red:
                red += 7

            # green is 6 bits
            green = int(rgb_data[5:11] + '00', 2)

            if green:
                green += 3

            # blue is 5 bits
            blue = int(rgb_data[11:] + '000', 2)

            if blue:
                blue += 7

            log.info(f'Packed RGB: {rgb_data}')
            log.info(f'Red: {red}')
            log.info(f'Green: {green}')
            log.info(f'Blue: {blue}')

            yield tuple([red, green, blue])
    except StopIteration:
        pass


def rgb_triplet_generator(pixel_data):
    """Yield (R, G, B) tuples for the provided pixel data."""
    iterator = iter(pixel_data)

    try:
        while True:
            # range(3) gives us 3 at a time, so r, g, b.
            yield tuple([next(iterator) for i in range(3)])
    except StopIteration:
        pass


def image_from_pixels(pixels, width, height):
    """Produce a pygame.image object for the specified [(R, G, B), ...] pixel data."""
    image = pygame.Surface((width, height))
    y = 0
    x = 0
    for pixel in pixels:
        image.fill(pixel, ((x, y), (1, 1)))

        if (x + 1) % width == 0:
            x = 0
            y += 1
        else:
            x += 1

    return image


def pixels_from_data(pixel_data):
    """Expand raw pixel data into [(R, G, B), ...] triplets."""
    pixels = rgb_triplet_generator(
        pixel_data=pixel_data,
    )

    # We are converting the data from a generator to
    # a list of data so that it can be referenced
    # multiple times.
    pixels = [pixel for pixel in pixels]  # noqa: R1721

    return pixels


def pixels_from_path(path):
    """Expand raw pixel data from file into [(R, G, B), ...] triplets."""
    with open(path, 'rb') as fh:
        pixel_data = fh.read()

    pixels = pixels_from_data(
        pixel_data=pixel_data
    )

    return pixels


class FontManager(ResourceManager):
    OPTIONS = {}
    RENDER_CACHE = {}

    class FontProxy(FontEvents, ResourceManager):
        def __init__(self, game=None):
            """
            """
            super().__init__(game=game)
            self.game = game
            self.proxies = [self.game, pygame.freetype]

    def __init__(self, game=None):
        """
        Manage fonts.

        FontManager manages fonts.

        Args:
        ----
        font - The name of the font to use.  Default: pygame.freetype.get_default_font()
        font_size - The size of the font to use. Default: 12
        font_bold - True for bold.  Default: False
        font_italic - True for italic. Default: False
        font_antialias - True for antialiased. Default: False
        font_dpi - Font DPI.  Default: 72

        """
        super().__init__(game=game)

        # Register pygame.freetype
        pygame.freetype.init()
        #pygame.font.init()
        #pygame.ftfont.init()

        log.info('Freetype Font Cache Size: '
                 f'{pygame.freetype.get_cache_size()}')
        log.info('Freetype Font Default Resolution: '
                 f'{pygame.freetype.get_default_resolution()}')

        # Set up the default options.
        FontManager.OPTIONS['font_name'] = game.OPTIONS['font_name']
        FontManager.OPTIONS['font_size'] = game.OPTIONS['font_size']
        FontManager.OPTIONS['font_bold'] = game.OPTIONS['font_bold']
        FontManager.OPTIONS['font_italic'] = game.OPTIONS['font_italic']
        FontManager.OPTIONS['font_antialias'] = game.OPTIONS['font_antialias']
        FontManager.OPTIONS['font_dpi'] = game.OPTIONS['font_dpi']

        pygame.freetype.set_default_resolution(FontManager.OPTIONS['font_dpi'])

        # Ideas:
        #
        # Pre-generate font cache based on settings that are provided.
        # Indexed by the letter they represent.
        # a -> <font name>
        # What about bold, italic, bold + italic, anti-aliased?
        # Maybe we can generate all combinations?
        # Allow caller to pass in a font settings blob and generate.
        # A progress bar class that integrates with tqdm?

        # Ideally, I'd like to support both modes.
        #
        # https://www.pygame.org/docs/ref/font.html
        # To use the pygame.freetypeEnhanced pygame module for loading
        # and rendering computer fonts based pygame.ftfont as pygame.fontpygame
        # module for loading and rendering fonts define the environment variable
        # PYGAME_FREETYPE before the first import of pygamethe top level pygame
        # package. Module pygame.ftfont is a pygame.fontpygame module for loading
        # and rendering fonts compatible module that passes all but one of the font
        # module unit tests: it does not have the UCS-2 limitation of the SDL_ttf
        # based font module, so fails to raise an exception for a code point greater
        # than 'uFFFF'. If pygame.freetypeEnhanced pygame module for loading and
        # rendering computer fonts is unavailable then the SDL_ttf font module
        # will be loaded instead.
        # pygame.ftfont.init()

        # self.proxies = [FontManager.FontProxy(game=game), pygame.freetype]

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Font Options')

        group.add_argument('--font-name',
                           default=pygame.freetype.get_default_font())
        group.add_argument('--font-size',
                           type=int,
                           default=14)
        group.add_argument('--font-bold',
                           action='store_true',
                           default=False)
        group.add_argument('--font-italic',
                           action='store_true',
                           default=False)
        group.add_argument('--font-antialias',
                           action='store_true',
                           default=False)
        group.add_argument('--font-dpi',
                           type=int,
                           default=72)

        return parser

    def font(self, font_config=None):  # noqa: R0201
        if not font_config:
            font_config = FontManager.OPTIONS

        return pygame.freetype.SysFont(name=font_config['font_name'],
                                       size=font_config['font_size'])


class MusicManager(ResourceManager):
    def __init__(self, game=None):  # noqa: W0235
        """
        Manage music.

        MusicManager manages music.

        Args:
        ----
        game -

        """
        super().__init__(game=game)

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Music Options')  # noqa: W0612

        return parser


class SoundManager(ResourceManager):
    def __init__(self, game=None):
        """
        Manage sounds.

        SoundManager manages sounds.

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

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Sound Mixer Options')  # noqa: W0612

        return parser

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

class MouseManager(ResourceManager):
    class MouseProxy(MouseEvents, ResourceManager):
        def __init__(self, game=None):
            """
            Pygame mouse event proxy.

            MouseProxy facilitates key handling by bridging mouse events between
            pygame and your game.

            Args:
            ----
            game - The game instance.

            """
            super().__init__(game)
            self.mouse_state = {}
            self.mouse_dragging = False
            self.mouse_dropping = False
            self.current_focus = None
            self.previous_focus = None
            self.focus_locked = False

            self.game = game
            self.proxies = [self.game, pygame.mouse]

        def on_mouse_motion_event(self, event):
            self.mouse_state[event.type] = event
            self.game.on_mouse_motion_event(event)

            # Figure out which item was clicked.
            mouse = MousePointer(x=event.pos[0], y=event.pos[1])

            collided_sprites = pygame.sprite.spritecollide(mouse, self.game.all_sprites, False)
            collided_sprite = None

            if collided_sprites:
                collided_sprite = collided_sprites[-1]

                # See if we're focused on the same sprite.
                if self.current_focus != collided_sprite:
                    # Newly focused object can "see" what the previously focused object was.
                    #
                    # Will be "None" if nothing is focused.
                    #
                    # We can use this to enable drag and drop.
                    #
                    # This will take care of the unfocus event, too.
                    self.on_mouse_focus_event(event, collided_sprite)
                    collided_sprite.on_mouse_enter_event(event)
                else:
                    # Otherwise, pass motion event to the focused sprite
                    # so it can handle sub-components if it wants to.
                    self.current_focus.on_mouse_motion_event(event)
            elif self.current_focus:
                # If we're focused on a sprite but the collide sprites list is empty, then
                # we're moving from a focus to empty space, and we should send an unfocus event.
                self.current_focus.on_mouse_exit_event(event)
                self.on_mouse_unfocus_event(event, self.current_focus)

            # Caller can check the buttons.
            # Note: This probably doesn't work right because
            # we aren't keeping track of button states.
            # We should be looking at all mouse states and emitting appropriately.
            for trigger in self.mouse_state.values():
                if trigger.type == pygame.MOUSEBUTTONDOWN:
                    self.on_mouse_drag_event(event, trigger)
                    self.mouse_dragging = True

        def on_mouse_drag_event(self, event, trigger):
            log.debug(f'{type(self)}: Mouse Drag: {event}')            
            self.game.on_mouse_drag_event(event, trigger)

            if self.focus_locked:
                if self.current_focus:
                    self.current_focus.on_mouse_drag_event(event, trigger)
                elif self.previous_focus:
                    self.previous_focus.on_mouse_drag_event(event, trigger)

            if trigger.button == 1:
                self.on_left_mouse_drag_event(event, trigger)
            if trigger.button == 2:
                self.on_middle_mouse_drag_event(event, trigger)
            if trigger.button == 3:
                self.on_right_mouse_drag_event(event, trigger)
            if trigger.button == 4:
                # This doesn't really make sense.
                pass
            if trigger.button == 5:
                # This doesn't really make sense.
                pass

        def on_mouse_drop_event(self, event, trigger):
            log.debug(f'{type(self)}: Mouse Drop: {event} {trigger}')
            self.game.on_mouse_drop_event(event, trigger)

            if self.focus_locked:
                if self.current_focus:
                    self.current_focus.on_mouse_drop_event(event, trigger)
                elif self.previous_focus:
                    self.previous_focus.on_mouse_drop_event(event, trigger)

            if trigger.button == 1:
                self.on_left_mouse_drop_event(event, trigger)
            if trigger.button == 2:
                self.on_middle_mouse_drop_event(event, trigger)
            if trigger.button == 3:
                self.on_right_mouse_drop_event(event, trigger)
            if trigger.button == 4:
                # This doesn't really make sense.
                pass
            if trigger.button == 5:
                # This doesn't really make sense.
                pass

        def on_left_mouse_drag_event(self, event, trigger):
            self.game.on_left_mouse_drag_event(event, trigger)

            if self.focus_locked:
                if self.current_focus:
                    self.current_focus.on_left_mouse_drag_event(event, trigger)
                elif self.previous_focus:
                    self.previous_focus.on_left_mouse_drag_event(event, trigger)

        def on_left_mouse_drop_event(self, event, trigger):
            self.game.on_left_mouse_drag_up_event(event, trigger)

            if self.focus_locked:
                if self.current_focus:
                    self.current_focus.on_left_mouse_drop_event(event, trigger)
                elif self.previous_focus:
                    self.previous_focus.on_left_mouse_drop_event(event, trigger)

        def on_middle_mouse_drag_event(self, event, trigger):
            self.game.on_middle_mouse_drag_down_event(event, trigger)

            if self.focus_locked:
                if self.current_focus:
                    self.current_focus.on_middle_mouse_drag_event(event, trigger)
                elif self.previous_focus:
                    self.previous_focus.on_middle_mouse_drag_event(event, trigger)

        def on_middle_mouse_drop_event(self, event, trigger):
            self.game.on_middle_mouse_drag_up_event(event, trigger)

            if self.focus_locked:
                if self.current_focus:
                    self.current_focus.on_middle_mouse_drop_event(event, trigger)
                elif self.previous_focus:
                    self.previous_focus.on_middle_mouse_drop_event(event, trigger)

        def on_right_mouse_drag_event(self, event, trigger):
            self.game.on_right_mouse_drag_down_event(event, trigger)

            if self.focus_locked:
                if self.current_focus:
                    self.current_focus.on_right_mouse_drag_event(event, trigger)
                elif self.previous_focus:
                    self.previous_focus.on_right_mouse_drag_event(event, trigger)

        def on_right_mouse_drop_event(self, event, trigger):
            self.game.on_right_mouse_drag_up_event(event, trigger)

            if self.focus_locked:
                if self.current_focus:
                    self.current_focus.on_right_mouse_drop_event(event, trigger)
                elif self.previous_focus:
                    self.previous_focus.on_right_mouse_drop_event(event, trigger)

        def on_mouse_focus_event(self, event, entering_focus):
            # Send a leave focus event for the old focus.
            if not self.focus_locked:
                self.on_mouse_unfocus_event(event, self.current_focus)

                # We've entered a new object.
                self.current_focus = entering_focus

                # Send an enter event for the new focus.
                entering_focus.on_mouse_focus_event(event, self.current_focus)

                log.info(f'Entered Focus: {self.current_focus}')
            else:
                log.info(f'Focus Locked: {self.previous_focus}')

        def on_mouse_unfocus_event(self, event, leaving_focus):
            self.previous_focus = leaving_focus

            if leaving_focus:
                leaving_focus.on_mouse_unfocus_event(event)
                self.current_focus = None

                log.info(f'Left Focus: {self.previous_focus}')

        def on_mouse_button_up_event(self, event):
            self.mouse_state[event.button] = event
            self.game.on_mouse_button_up_event(event)

            if event.button == 1:
                self.on_left_mouse_button_up_event(event)
            if event.button == 2:
                self.on_middle_mouse_button_up_event(event)
            if event.button == 3:
                self.on_right_mouse_button_up_event(event)
            if event.button == 4:
                # This doesn't really make sense.
                pass
            if event.button == 5:
                # This doesn't really make sense.
                pass
            
            if self.mouse_dragging:
                # The mouse up location is also the trigger.
                self.game.on_mouse_drop_event(event=event, trigger=event)
                self.mouse_dragging = False

            # Whatever was locked gets unlocked.
            self.focus_locked = False

        def on_left_mouse_button_up_event(self, event):
            self.game.on_left_mouse_button_up_event(event)

        def on_middle_mouse_button_up_event(self, event):
            self.game.on_middle_mouse_button_up_event(event)

        def on_right_mouse_button_up_event(self, event):
            self.game.on_right_mouse_button_up_event(event)

        def on_mouse_button_down_event(self, event):
            self.mouse_state[event.button] = event

            # Whatever was clicked on gets lock.
            if self.current_focus:
                self.focus_locked = True

            if event.button == 1:
                self.on_left_mouse_button_down_event(event)
            if event.button == 2:
                self.on_middle_mouse_button_down_event(event)
            if event.button == 3:
                self.on_right_mouse_button_down_event(event)
            if event.button == 4:
                self.on_mouse_scroll_down_event(event)
            if event.button == 5:
                self.on_mouse_scroll_up_event(event)

            self.game.on_mouse_button_down_event(event)

        def on_left_mouse_button_down_event(self, event):
            self.game.on_left_mouse_button_down_event(event)

        def on_middle_mouse_button_down_event(self, event):
            self.game.on_middle_mouse_button_down_event(event)

        def on_right_mouse_button_down_event(self, event):
            self.game.on_right_mouse_button_down_event(event)

        def on_mouse_scroll_down_event(self, event):
            self.game.on_mouse_scroll_down_event(event)

        def on_mouse_scroll_up_event(self, event):
            self.game.on_mouse_scroll_up_event(event)

    def __init__(self, game=None):
        """
        Mouse event manager.

        MouseManager interfaces GameEngine with MouseManager.MouseManagerProxy.

        Args:
        ----
        game - The game instance.

        """
        super().__init__(game=game)
        self.proxies = [MouseManager.MouseProxy(game=game)]


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
            joystick_info.append(f'Joystick Name: self.get_name()')
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


class GameManager(ResourceManager):
    class GameProxy(ResourceManager):
        def __init__(self, **kwargs):
            """
            Game event proxy.

            GameProxy facilitates custom and otherwise unhandled pygame
            events between pygame and your game.

            Args:
            ----
            joystick_id - the id of the joystick to init
            game - The game instance.

            """
            super().__init__(**kwargs)
            self.game = kwargs.get('game')
            self.proxies = [self.game]

        def on_active_event(self, event):
            self.game.on_active_event(event)

    def __init__(self, game=None):
        """
        Game event manager.

        GameManager interfaces GameEngine with miscellaneous pygame events.

        Args:
        ----
        game - The game instance.

        """
        super().__init__(game=game)
        self.proxies = [GameManager.GameProxy(game=game)]

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Game Options')  # noqa: W0612

        return parser

def supported_events(like='.*'):
    # Get a list of all of the events
    # by name, but ignore duplicates.
    event_names = [*set(pygame.event.event_name(event_num)
                        for event_num in range(0, pygame.NUMEVENTS))]
    event_names = set(event_names) - set('Unknown')
    event_list = []

    for event_name in list(event_names):
        try:
            if re.match(like, event_name.upper()):
                event_list.append(getattr(pygame, event_name.upper()))
                log.info(event_name.upper())
        except AttributeError as e:
            log.error(f'Failed to init: {e}')

    return event_list


class GameEngine(EventManager):
    NAME = "Boilerplate Adventures"
    VERSION = "1.0"
    FPS = 0
    OPTIONS = None

    FPSEVENT = pygame.USEREVENT + 1
    GAMEEVENT = pygame.USEREVENT + 2
    MENUEVENT = pygame.USEREVENT + 3

    MOUSE_EVENTS = supported_events(like='MOUSE.*?')
    KEYBOARD_EVENTS = supported_events(like='KEY.*?')
    JOYSTICK_EVENTS = supported_events(like='JOY.*?')
    ALL_EVENTS = supported_events()
    GAME_EVENTS = list(set(ALL_EVENTS) -
                       set(MOUSE_EVENTS) -
                       set(KEYBOARD_EVENTS) -
                       set(JOYSTICK_EVENTS))

    GAME_EVENTS.append(FPSEVENT)
    GAME_EVENTS.append(GAMEEVENT)
    GAME_EVENTS.append(MENUEVENT)

    def __init__(self, game=None, options=None):
        """
        Set up pygame and handle events.

        Your game should subclass this class.

        Args:
        ----
        game - None, since it *is* the game.
        options - the configuration options passed via the command line.

        """
        # Persist this game's options.
        GameEngine.OPTIONS = options

        super().__init__(game=self)

        self._active_scene = None

        # Pygame stuff.
        pygame.register_quit(self.quit)
        self.fps = options.get('fps', 0)
        self.update_type = options.get('update_type')
        self.use_gfxdraw = options.get('use_gfxdraw')
        self.windowed = options.get('windowed')
        self.desired_resolution = options.get('resolution')
        self.fps_refresh_rate = options.get('fps_refresh_rate')

        # Initialize all of the Pygame modules.
        self.init_pass, self.init_fail = pygame.init()
        self.print_game_info()

        # Enable fast events for multithreaded applications
        pygame.fastevent.init()

        self.clock = pygame.time.Clock()

        self.registered_events = {}
        self.game_manager = GameManager(self)
        self.mouse_manager = MouseManager(self)
        self.keyboard_manager = KeyboardManager(self)
        self.sound_manager = SoundManager(self)
        self.music_manager = MusicManager(self)
        self.font_manager = FontManager(self)
        self.joystick_manager = JoystickManager(self)

        # Get count of joysticks
        self.joysticks = []
        if self.joystick_manager:
            self.joysticks = self.joystick_manager.joysticks
        self.joystick_count = len(self.joysticks)

        # Resolution initialization.
        # Convert our resolution to a tuple
        (desired_width, desired_height) = self.desired_resolution.split('x')

        if self.windowed:
            self.mode_flags = 0
        else:
            self.mode_flags = pygame.FULLSCREEN

        self.desired_resolution = self.suggested_resolution(desired_width, desired_height)

        # window icon and system tray/dock icon
        self.initialize_system_icons()

        # Let's try to set a resolution to the most compatible for
        # the system.  If we don't provide any parameters, we'll get
        # a reasonble default, but you should consider whether that's
        # a good idea for your particular application.
        #
        # There are various caveats for hardware accelerated blitting
        # that make it undesirable in a lot of cases, so we'll just use
        # software.
        self.display_info = pygame.display.Info()
        self.initial_resolution = (self.display_info.current_w,
                                   self.display_info.current_h)

        self.cursor = self.set_cursor(cursor=None)

        # Set the screen update type.
        if self.update_type == 'update':
            self.display_update = pygame.display.update
        elif self.update_type == 'flip':
            self.display_update = pygame.display.flip
        else:
            log.error('Screen update type was neither "update" nor "flip".')

        # The Pygame documentation recommends against using hardware accelerated blitting.
        #
        # Note that you can also get the screen with pygame.display.get_surface()
        self.screen = pygame.display.set_mode(self.desired_resolution,
                                              self.mode_flags)

        self.print_system_info()

    def __del__(self):
        # This is the total # of sprites.
        log.info(f'Sprite Count: {RootSprite.SPRITE_COUNT}')

        # This is a count of each type of sprite.
        for sprite_type, counters in RootSprite.SPRITE_COUNTERS.items():
            #sprite_count = RootSprite.SPRITE_COUNTERS[sprite_type][key]            
            for key, value in counters.items():
                log.info(f'{sprite_type} Sprite {key}: {value}')
    @property
    def screen_width(self):
        return self.screen.get_width()

    @property
    def screen_height(self):
        return self.screen.get_height()

    def print_system_info(self):
        # General Info
        log.info(f'CPU Count: {multiprocessing.cpu_count()}')
        log.info(f'System: {platform.system()}')
        log.info(f'Machine: {platform.machine()}')
        log.info(f'Platform: {platform.platform()}')
        log.info(f'Platform (Terse): {platform.platform(aliased=0, terse=1)}')
        log.info(f'Processor: {platform.processor()}')
        log.info(f'Release: {platform.release()}')

        # Set up a display mode.
        # Note: pygame.display.init() isn't necessary here
        # because we've already called pygame.init() which
        # initializes all available modules.
        #
        # Let's do a sanity check and make sure we're initialized.
        log.info(f'Display inited: {pygame.display.get_init()}')

        # Display some configuration information.
        log.info(f'SDL Version: {pygame.get_sdl_version()}')
        log.info(f'SDL Byte Order: {pygame.get_sdl_byteorder()}')

        # Dump a bit more info about the configured mode.
        log.info('Display Driver: '
                 f'{pygame.display.get_driver()}')
        log.info('Display Info: '
                 f'{self.display_info}')
        log.info('Initial Resolution: '
                 f'{self.initial_resolution}')
        log.info('8-bit Modes: '
                 f'{pygame.display.list_modes(8)}')
        log.info('16-bit Modes: '
                 f'{pygame.display.list_modes(16)}')
        log.info('24-bit Modes: '
                 f'{pygame.display.list_modes(24)}')
        log.info('32-bit Modes: '
                 f'{pygame.display.list_modes(32)}')
        log.info('Best Color Depth: '
                 f'{pygame.display.mode_ok(self.initial_resolution), self.mode_flags}'
                 f' ({self.mode_flags})')
        log.info('Window Manager Info: '
                 f'{pygame.display.get_wm_info()}')
        log.info('Platform Timer Resolution: '
                 f'{pygame.TIMER_RESOLUTION}')

    def print_game_info(self):
        log.debug(f'Successfully loaded {self.init_pass} modules '
                  f'and failed loading {self.init_fail} modules.')

        log.info('Game Title: '
                 f'{type(self).NAME}')
        log.info('Game Version: '
                 f'{type(self).VERSION}')

    def suggested_resolution(self, desired_width=0, desired_height=0):  # noqa: R0201
        # For Ubuntu 19.04, we can't reset the original res
        # so let's just let the system figure it out.
        if platform.system() == 'Linux':
            if 'arm' not in platform.machine():
                log.info('Ignoring full screen resolution change on Linux.')
            else:
                # RPi Hack
                #
                # The Raspberry Pi screen exposes
                # 2 resolutions, but only one works properly
                desired_width = 800
                desired_height = 480

        return (int(desired_width), int(desired_height))

    def set_cursor(self, cursor=None, cursor_black='.', cursor_white='X', cursor_xor='o'):  # noqa R0201
        if not cursor:
            # Cursor setup.
            # Cursor width/height must be a multiple of 8
            cursor = [
                "XX                      ",
                "XXX                     ",
                "XXXX                    ",
                "XX.XX                   ",
                "XX..XX                  ",
                "XX...XX                 ",
                "XX....XX                ",
                "XX.....XX               ",
                "XX......XX              ",
                "XX.......XX             ",
                "XX........XX            ",
                "XX........XXX           ",
                "XX......XXXXX           ",
                "XX.XXX..XX              ",
                "XXXX XX..XX             ",
                "XX   XX..XX             ",
                "     XX..XX             ",
                "      XX..XX            ",
                "      XX..XX            ",
                "       XXXX             ",
                "       XX               ",
                "                        ",
                "                        ",
                "                        "]

        cursor_width = len(cursor[0])
        cursor_height = len(cursor)

        # cursor = cursor

        # Compile our cursor so we can draw it to the screen.
        cursor_data, cursor_mask = pygame.cursors.compile(cursor,
                                                          black=cursor_black,
                                                          white=cursor_white,
                                                          xor=cursor_xor)

        # Now set the cursor as the active cursor.
        pygame.mouse.set_cursor((cursor_width, cursor_height),
                                (0, 0),
                                cursor_data,
                                cursor_mask)

        return cursor

    def initialize_system_icons(self):
        # Set the window icon.
        #
        # Always call this before you call set_mode()
        icon = pygame.Surface((32, 32))
        icon.fill(PURPLE)
        pygame.display.set_icon(icon)

        # Set the display caption.
        pygame.display.set_caption(f'{type(self).NAME}',
                                   f'{type(self).NAME}')

        # Get captions:
        (title, icontitle) = pygame.display.get_caption()
        log.info(f'Window Title: {title}')
        log.info(f'Icon Title: {icontitle}')

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Graphics Options')

        group.add_argument('-f', '--fps',
                           help='cap the framerate (default: infinite)',
                           type=float,
                           default=0.0)
        group.add_argument('--fps-refresh-rate',
                           help='how often to update the FPS counter in ms (default: 1000)',
                           default=1000)
        group.add_argument('-w', '--windowed',
                           help='run the program in windowed mode',
                           action='store_true',
                           default=True)
        group.add_argument('-r', '--resolution',
                           help='the resolution to use (default: 1024x768)',
                           default='800x480')
        group.add_argument('--use-gfxdraw',
                           action='store_true',
                           default=False)
        group.add_argument('--update-type',
                           help='update or flip (default: update)',
                           choices=['update', 'flip'],
                           default='update')

        # See https://www.pygame.org/docs/ref/display.html#pygame.display.set_mode
        default_videodriver = []
        if platform.system() == 'Linux':
            linux_videodriver_choices = ['x11',
                                         'dga',
                                         'fbcon',
                                         'directfb',
                                         'ggi',
                                         'vgl',
                                         'svgalib',
                                         'aalib']

            log.debug(f'Linux Video Driver Choices: {linux_videodriver_choices}')

            default_videodriver = linux_videodriver_choices

        elif platform.system() == 'MacOS':
            mac_videodriver_choices = []

            log.debug(f'Mac Video Driver Choices: {mac_videodriver_choices}')
            default_videodriver = mac_videodriver_choices
        elif platform.system() == 'Windows':
            windows_videodriver_choices = ['windib', 'directx']

            log.debug(f'Windows Video Driver Choices: {windows_videodriver_choices}')
            default_videodriver = windows_videodriver_choices

        group.add_argument('--video-driver',
                           default=None,
                           choices=default_videodriver)

        # Init Font Options
        parser = FontManager.args(parser=parser)

        # Init Sound Options
        parser = SoundManager.args(parser=parser)

        # Init Music Options
        parser = MusicManager.args(parser=parser)

        return parser

    def start(self):
        log.info(f'Framerate check (configured FPS: {self.fps})')

        # On Some platforms, pygame.USEREVENT is used to convey codes
        # so, we'll use USEREVENT + 1 to avoid confusion.
        pygame.time.set_timer(
            GameEngine.FPSEVENT,
            self.fps_refresh_rate
        )

        self._active_scene = None

    def quit(self):  # noqa: R0201
        # put a quit event in the event queue.
        pygame.event.post(
            pygame.event.Event(pygame.QUIT, {})
        )

    @property
    def active_scene(self):
        return self._active_scene

    @active_scene.setter
    def active_scene(self, new_scene):
        if new_scene != self._active_scene:
            log.debug(f'Active Scene change from {type(self._active_scene)}->{type(new_scene)}')
            self._active_scene = new_scene
            self.proxies = [self, self._active_scene]

    def load_resources(self):  # noqa: R0201
        log.info('Implement load_resource() in your subclass.')

    def process_events(self):
        # To use events in a different thread, use the fastevent package from pygame.
        # You can create your own new events with the pygame.event.Event() function.
        for event in pygame.fastevent.get():
            if event.type in GameEngine.GAME_EVENTS:
                self.process_game_event(event)
            elif event.type in GameEngine.JOYSTICK_EVENTS:
                self.process_joystick_event(event)
            elif event.type in GameEngine.MOUSE_EVENTS:
                self.process_mouse_event(event)
            elif event.type in GameEngine.KEYBOARD_EVENTS:
                self.process_keyboard_event(event)
            else:
                # This will catch any unimplemented event types that we see.
                log.error(f'Unknown Event Type: {event.type}: {event} {GameEngine.ALL_EVENTS}')

    def process_mouse_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            # MOUSEMOTION      pos, rel, buttons
            self.mouse_manager.on_mouse_motion_event(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            # MOUSEBUTTONUP    pos, button
            self.mouse_manager.on_mouse_button_up_event(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # MOUSEBUTTONDOWN  pos, button
            self.mouse_manager.on_mouse_button_down_event(event)

    def process_keyboard_event(self, event):
        if event.type == pygame.KEYDOWN:
            # KEYDOWN          unicode, key, mod
            self.keyboard_manager.on_key_down_event(event)
        elif event.type == pygame.KEYUP:
            # KEYUP            key, mod
            self.keyboard_manager.on_key_up_event(event)

    def process_joystick_event(self, event):
        if event.type == pygame.JOYAXISMOTION:
            # JOYAXISMOTION    joy, axis, value
            self.joystick_manager.on_axis_motion_event(event)
        elif event.type == pygame.JOYBALLMOTION:
            # JOYBALLMOTION    joy, ball, rel
            self.joystick_.on_ball_motion_event(event)
        elif event.type == pygame.JOYHATMOTION:
            # JOYHATMOTION     joy, hat, value
            self.joystick_manager.on_hat_motion_event(event)
        elif event.type == pygame.JOYBUTTONUP:
            # JOYBUTTONUP      joy, button
            self.joystick_manager.on_button_up_event(event)
        elif event.type == pygame.JOYBUTTONDOWN:
            # JOYBUTTONDOWN    joy, button
            self.joystick_manager.on_button_down_event(event)

    def process_game_event(self, event):
        if event.type == GameEngine.FPSEVENT:
            # FPSEVENT is pygame.USEREVENT + 1
            self.game_manager.on_fps_event(event)
        elif event.type == GameEngine.GAMEEVENT:
            # GAMEEVENT is pygame.USEREVENT + 2
            self.game_manager.on_game_event(event)
        elif event.type == GameEngine.MENUEVENT:
            # MENUEVENT is pygame.USEREVENT + 3
            self.game_manager.on_menu_item_event(event)
        elif event.type == pygame.USEREVENT:
            # USEREVENT        code
            self.game_manager.on_user_event(event)
        elif event.type == pygame.QUIT:
            # QUIT             none
            self.game_manager.on_quit_event(event)
        elif event.type == pygame.ACTIVEEVENT:
            # ACTIVEEVENT      gain, state
            self.game_manager.on_active_event(event)
        elif event.type == pygame.VIDEORESIZE:
            # VIDEORESIZE      size, w, h
            self.game_manager.on_video_resize_event(event)
        elif event.type == pygame.VIDEOEXPOSE:
            # VIDEOEXPOSE      none
            self.game_manager.on_video_expose_event(event)
        elif event.type == pygame.SYSWMEVENT:
            # SYSWMEVENT
            self.game_manager.on_sys_wm_event(event)

    def register_game_event(self, event_type, callback):
        # This registers a subtype of type GAMEEVENT to call a callback.
        log.info(f'Registering event type "{event_type}" for {callback}')
        self.registered_events[event_type] = callback

    def post_game_event(self, event_subtype, event_data):  # noqa: R0201
        event = event_data.copy()
        event['subtype'] = event_subtype
        pygame.event.post(
            pygame.event.Event(GameEngine.GAMEEVENT, event)
        )
        log.debug(f'Posted Event: {event}')

    def on_fps_event(self, event):
        # FPSEVENT is pygame.USEREVENT + 1
        GameEngine.FPS = self.clock.get_fps()
        self.active_scene.on_fps_event(event)

    def on_game_event(self, event):
        # GAMEEVENT is pygame.USEREVENT + 2
        # Call the event callback if it's registered.
        try:
            self.registered_events[event.subtype](event)
        except KeyError:
            log.error(f'Unregistered Event: {event} '
                      '(call self.register_game_event(<event subtype>, <event data>))')

    def on_key_up_event(self, event):
        # Wire up quit by default for escape and q.
        #
        # If a game implements on_key_up_event themselves
        # they'll have to map their quit keys or call super().on_key_up_event()
        if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
            log.info('User requested quit.')
            self.quit()

    # If the game hasn't hooked a call, we should check if the scene manager has.
    #
    # This will allow scenes to get pygame events directly, but we can still
    # hook those events in this engine, or in the subclassed game object, too.
    #
    # This allows maximum flexibility of event processing, with low overhead
    # at the expense of a slight layer violation.
    def __getattr__(self, attr):
        # Attempt to proxy the call to the active scene.
        try:
            log.info(f'ACTIVE SCENE: {attr} for {type(self)}')
            return getattr(self.active_scene, attr)
        except AttributeError:
            log.info(f'{attr} is not implemented for {type(self)} or '
                     'for the active scene {type(self.active_scene)}')
            return getattr(super(), attr)


class RootScene(EventManager):
    def __init__(self, groups=pygame.sprite.LayeredDirty()):
        """
        Scene object base class.

        Subclass this to properly receive on_*_event() messages automatically.
        """
        super().__init__()
        # This will resolve to the class name of any subclass.
        self.name = type(self)
        self.background_color = BLACK
        self.next = self
        self.rects = None

        # http://n0nick.github.io/blog/2012/06/03/quick-dirty-using-pygames-dirtysprite-layered/
        self.all_sprites = groups

        # Initial screen state.

        self.screen = pygame.display.get_surface()
        self.background = pygame.Surface(self.screen.get_size())
        self.background.convert()
        self.background.fill(self.background_color)

        # I don't think this will work since init() is called first.
        # for group in groups:
        #    for sprite in self.all_sprites:
        #        group.add(sprite)

        self.all_sprites.clear(self.screen, self.background)

    def update(self):
        self.rects = self.all_sprites.draw(self.screen)

    def render(self, screen):  # noqa: W0613
        self.all_sprites.update()

    def switch_to_scene(self, next_scene):
        self.next = next_scene

    def terminate(self):
        self.switch_to_scene(None)

    def sprites_at_position(self, pos):
        mouse = MousePointer(x=pos[0], y=pos[1])

        return pygame.sprite.spritecollide(mouse, self.all_sprites, False)

    def on_mouse_drag_event(self, event, trigger):
        log.debug(f'{type(self)}: Mouse Drag Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_mouse_drag_event(event, trigger)

    def on_mouse_drop_event(self, event, trigger):
        log.debug(f'{type(self)}: Mouse Drop Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_mouse_drop_event(event, trigger)            

    def on_left_mouse_drag_event(self, event, trigger):
        log.debug(f'{type(self)}: Left Mouse Drag Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        if collided_sprites:
            collided_sprites[-1].on_left_mouse_drag_event(event, trigger)
        
        #for sprite in collided_sprites:
        #    sprite.on_left_mouse_drag_event(event, trigger)

    def on_left_mouse_drop_event(self, event, trigger):
        log.debug(f'{type(self)}: Left Mouse Drop Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_left_mouse_drop_event(event, trigger)

    def on_middle_mouse_drag_event(self, event, trigger):
        log.info(f'{type(self)}: Middle Mouse Drag Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_drag_event(event, trigger)

    def on_middle_mouse_drop_event(self, event, trigger):
        log.info(f'{type(self)}: Middle Mouse Drop Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_drop_event(event, trigger)

    def on_right_mouse_drag_event(self, event, trigger):
        log.info(f'{type(self)}: Right Mouse Drag Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_drag_event(event, trigger)

    def on_right_mouse_drop_event(self, event, trigger):
        log.info(f'{type(self)}: Right Mouse Drop Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_drop_event(event, trigger)

    def on_left_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        log.debug(f'{type(self)}: Left Mouse Button Up Event: {event}')

        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_left_mouse_button_up_event(event)

    def on_middle_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        log.debug(f'{type(self)}: Middle Mouse Button Up Event: {event}')

        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_button_up_event(event)

    def on_right_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        log.info(f'{type(self)}: Right Mouse Button Up Event: {event}')

        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_button_up_event(event)

    def on_left_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        log.debug(f'{type(self)}: Left Mouse Button Down Event: {event}')

        collided_sprites = self.sprites_at_position(pos=event.pos)

        log.info(f'ENGINE SPRITES: {collided_sprites}')

        #if collided_sprites:
        #    collided_sprites[0].on_left_mouse_button_down_event(event)
        for sprite in collided_sprites:
            sprite.on_left_mouse_button_down_event(event)

    def on_middle_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN    pos, button
        log.debug(f'{type(self)}: Middle Mouse Button Down Event: {event}')

        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_button_down_event(event)

    def on_right_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        log.info(f'{type(self)}: Right Mouse Button Down Event: {event}')

        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_button_down_event(event)

    def on_quit_event(self, event):
        # QUIT             none
        log.debug(f'{type(self)}: {event}')
        self.terminate()

    def on_fps_event(self, event):  # noqa: W0613
        # FPSEVENT is pygame.USEREVENT + 1
        log.info(f'{type(self)}: {GameEngine.FPS}')


class RootRootSprite(pygame.sprite.DirtySprite):
    def __init__(self, groups=pygame.sprite.LayeredDirty()):
        super().__init__(groups)


class RootSprite(MouseEvents, pygame.sprite.DirtySprite):
    """A convenience class for handling all of the common sprite behaviors."""

    USE_GFXDRAW = False
    PROXIES = [pygame.sprite]
    SPRITE_BREAKPOINTS = None  # None means no breakpoints.  Empty list means all.
    SPRITE_COUNTERS = collections.OrderedDict()
    SPRITE_COUNT = 0

    @classmethod
    def break_when(cls, sprite_type=None):
        # None means disabled.
        # [] means any.
        if cls.SPRITE_BREAKPOINTS is None:
            cls.SPRITE_BREAKPOINTS = []
        
        # If none, break always.
        if sprite_type is not None:
            log.info(f'Register break when sprite_type=={cls}')
            cls.SPRITE_BREAKPOINTS.append(str(cls))
        else:
            log.info('Register break when sprite_type==<any>')

    def __init__(self, x, y, width, height, name=None, groups=pygame.sprite.LayeredDirty()):  # noqa: W0613
        super().__init__(groups)

        self.x = x
        self.y = y

        self.width = int(width)
        self.height = int(height)
        self.name = name
        self.proxies = [self]

        # For debugging sanity.
        if not name:
            self.name = type(self)

        if not self.width:
            log.error(f'{type(self)} has 0 Width')

        if not self.height:
            log.error(f'{type(self)} has 0 Height')

        # Sprites can register callbacks for any event type.
        self.callbacks = {}

        # Each sprite maintains a reference to the screen.
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        # This is the stuff pygame really cares about.
        self.image = pygame.Surface((self.width, self.height))
        self.rect = self.image.get_rect()

        groups.add(self)

        # Add ourselves to the sprite counters.
        my_type = str(type(self))
        
        if my_type in self.SPRITE_COUNTERS:
            self.SPRITE_COUNTERS[my_type]['count'] += 1
            self.SPRITE_COUNTERS[my_type]['pixels'] = self.width * self.height + self.SPRITE_COUNTERS[my_type]['pixels']
        else:
            self.SPRITE_COUNTERS[my_type] = collections.OrderedDict()
            self.SPRITE_COUNTERS[my_type]['count'] = 1
            self.SPRITE_COUNTERS[my_type]['pixels'] = 0
        self.SPRITE_COUNT += 1

        # None means disabled.
        if self.SPRITE_BREAKPOINTS is not None:
            # Empty list means all.
            if len(self.SPRITE_BREAKPOINTS) == 0:
                log.info(f'Break when sprite_type=={str(type(self))}')
                import pdb; pdb.set_trace()
            else:
                for sprite_type in self.SPRITE_BREAKPOINTS:
                    import pdb; pdb.set_trace()                    
                    if str(type(self)) == sprite_type:
                        log.info(f'Break when sprite_type==<any>')                        
                        import pdb; pdb.set_trace()
            
            

    def update(self):
        pass

    def on_axis_motion_event(self, event):
        # JOYAXISMOTION    joy, axis, value
        log.debug(f'{type(self)}: {event}')

    def on_button_down_event(self, event):
        # JOYBUTTONDOWN    joy, button
        log.debug(f'{type(self)}: {event}')

    def on_button_up_event(self, event):
        # JOYBUTTONUP      joy, button
        log.debug(f'{type(self)}: {event}')

    def on_hat_motion_event(self, event):
        # JOYHATMOTION     joy, hat, value
        log.debug(f'{type(self)}: {event}')

    def on_ball_motion_event(self, event):
        # JOYBALLMOTION    joy, ball, rel
        log.debug(f'{type(self)}: {event}')

    def on_mouse_motion_event(self, event):
        # MOUSEMOTION      pos, rel, buttons
        log.debug(f'Mouse Motion Event: {type(self)}: {event}')

    def on_mouse_focus_event(self, event, old_focus):
        # Custom Event
        log.debug(f'Mouse Focus Event: {type(self)}: {event}, Old Focus: {old_focus}')

    def on_mouse_unfocus_event(self, event):
        # Custom Event
        log.debug(f'Mouse Unfocus Event: {type(self)}: {event}')

    def on_mouse_enter_event(self, event):
        # Custom Event
        log.debug(f'Mouse Enter Event: {type(self)}: {event}')

    def on_mouse_exit_event(self, event):
        # Custom Event
        log.debug(f'Mouse Exit Event: {type(self)}: {event}')

    def on_mouse_drag_down_event(self, event, trigger):
        log.debug(f'Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}')

    def on_left_mouse_drag_down_event(self, event, trigger):
        log.debug(f'Left Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}')

    def on_left_mouse_drag_up_event(self, event, trigger):
        log.debug(f'Left Mouse Drag Up Event: {type(self)}: event: {event}, trigger: {trigger}')

    def on_middle_mouse_drag_down_event(self, event, trigger):
        log.debug(f'Middle Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}')

    def on_middle_mouse_drag_up_event(self, event, trigger):
        log.debug(f'Middle Mouse Drag Up Event: {type(self)}: event: {event}, trigger: {trigger}')

    def on_right_mouse_drag_down_event(self, event, trigger):
        log.debug(f'Right Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}')

    def on_right_mouse_drag_up_event(self, event, trigger):
        log.debug(f'Right Mouse Drag Up Event: {type(self)}: event: {event}, trigger: {trigger}')

    def on_mouse_drag_up_event(self, event):
        log.debug(f'Mouse Drag Up Event: {type(self)}: {event}')

    def on_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        log.debug(f'{type(self)}: {event}')

    def on_left_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button

        if self.callbacks:
            callback = self.callbacks.get('on_left_mouse_button_up_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            log.debug(f'{type(self)}: Left Mouse Button Up Event: {event} @ {self}')

    def on_middle_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        log.debug(f'{type(self)}: Middle Mouse Button Up Event: {event}')

    def on_right_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        if self.callbacks:
            callback = self.callbacks.get('on_right_mouse_button_up_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            log.debug(f'{type(self)}: Right Mouse Button Up Event: {event} @ {self}')

    def on_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        log.debug(f'{type(self)}: {event} @ {self}')

    def on_left_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        callback = 'on_left_mouse_button_down_event'

        if self.callbacks:
            callback = self.callbacks.get('on_left_mouse_button_down_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            log.debug(f'{type(self)}: Left Mouse Button Down Event: {event} @ {self}')

    def on_middle_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        log.debug(f'{type(self)}: Middle Mouse Button Down Event: {event}')

    def on_right_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        if self.callbacks:
            callback = self.callbacks.get('on_right_mouse_button_down_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            log.debug(f'{type(self)}: Right Mouse Button Down Event: {event} @ self')

    def on_mouse_scroll_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        log.debug(f'{type(self)}: Mouse Scroll Down Event: {event}')

    def on_mouse_scroll_up_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        log.debug(f'{type(self)}: Mouse Scroll Up Event: {event}')

    def on_mouse_chord_up_event(self, event):
        log.debug(f'{type(self)}: Mouse Chord Up Event: {event}')

    def on_mouse_chord_down_event(self, event):
        log.debug(f'{type(self)}: Mouse Chord Down Event: {event}')

    def on_key_down_event(self, event):
        # KEYDOWN          unicode, key, mod
        log.debug(f'{type(self)}: {event}')

    def on_key_up_event(self, event):
        # KEYUP            key, mod
        log.debug(f'{type(self)}: {event}')

    def on_key_chord_down_event(self, event, keys):
        log.debug(f'{type(self)}: {event}, {keys}')

    def on_key_chord_up_event(self, event, keys):
        log.debug(f'{type(self)} KEYCHORDUP: {event}, {keys}')

    def on_quit_event(self, event):
        # QUIT             none
        log.debug(f'{type(self)}: {event}')
        self.terminate()

    def on_active_event(self, event):
        # ACTIVEEVENT      gain, state
        log.debug(f'{type(self)}: {event}')

    def on_video_resize_event(self, event):
        # VIDEORESIZE      size, w, h
        log.debug(f'{type(self)}: {event}')

    def on_video_expose_event(self, event):
        # VIDEOEXPOSE      none
        log.debug(f'{type(self)}: {event}')

    def on_sys_wm_event(self, event):
        # SYSWMEVENT
        log.debug(f'{type(self)}: {event}')

    def on_user_event(self, event):
        # USEREVENT        code
        log.debug(f'{type(self)}: {event}')

    def on_fps_event(self, event):  # noqa: W0613
        # FPSEVENT is pygame.USEREVENT + 1
        log.debug(f'{type(self)}: {GameEngine.FPS}')

    # def __getattr__(self, attr):
    #    import pdb; pdb.set_trace()
        # Try each proxy in turn
   #     for proxy in type(self).PROXIES:
   #         try:
   #             it = getattr(super(), attr)
   #             import pdb; pdb.set_trace()
   #             return getattr(proxy, attr)
   #         except AttributeError:
   #             log.error(f'No proxies for {type(self)}.{attr}')

    def __str__(self):
        return f'{type(self)} "{self.name}" ({repr(self)})'


class BitmappySprite(RootSprite):
    DEBUG = False
    # __instance__ = None

    # def __new__(cls, *args, **kwargs):
    #    cls.__instance__ = object.__new__(cls)
    #    cls.__instance__.args = args
    #    cls.__instance__.kwargs = kwargs
    #    log.info(f'Args: {args}, Kwargs: {kwargs}')
    #    return cls.__instance

    def __init__(self, x, y, width, height, name=None, filename=None,
                 groups=pygame.sprite.LayeredDirty()):
        """
        Subclass to load sprite files.

        Args:
        ----
        filename - optional, the BitmappySprite config to load.

        """
        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)
        self.filename = filename
        # self.width = width
        # self.height = height

        # Try to load a file if one was specified, otherwise
        # if a width and height is specified, make a surface.
        if filename:
            (self.image, self.rect, self.name) = self.load(filename=filename)
            self.width = self.rect.width
            self.height = self.rect.height

        elif self.width and self.height:
            self.image = pygame.Surface((self.width, self.height))
            self.image.convert()
        else:
            raise Exception(f"Can't create Surface(({self.width}, {self.height})).")

        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y

    def load(self, filename):  # noqa: R0914
        config = configparser.ConfigParser(dict_type=collections.OrderedDict,
                                           empty_lines_in_values=True,
                                           strict=True)

        config.read(filename)

        # [sprite]
        # name = <name>
        name = config.get(section='sprite', option='name')

        # pixels = <pixels>
        pixels = config.get(section='sprite', option='pixels').split('\n')

        # Set our sprite's length and width.
        width = 0
        height = 0
        index = -1

        # This is a bit of a cleanup in case the config contains something like:
        #
        # pixels = \n
        #  .........
        #
        while not width:
            index += 1
            width = len(pixels[index])
            height = len(pixels[index:])

        # Trim any dead whitespace.
        # We're off by one since we increment the
        pixels = pixels[index:]

        color_map = {}
        for section in config.sections():
            # This is checking the length of the section's name.
            # Colors are length 1.  This works with unicode, too.
            if len(section) == 1:
                red = config.getint(section=section, option='red')
                green = config.getint(section=section, option='green')
                blue = config.getint(section=section, option='blue')

                color_map[section] = (red, green, blue)

        (image, rect) = self.inflate(width=width,
                                     height=height,
                                     pixels=pixels,
                                     color_map=color_map)

        return (image, rect, name)

    def inflate(self, width, height, pixels, color_map):  # noqa: R0201
        image = pygame.Surface((width, height))
        image.convert()

        raw_pixels = []
        for y, row in enumerate(pixels):
            for x, pixel in enumerate(row):
                color = color_map[pixel]
                raw_pixels.append(color)
                pygame.draw.rect(image, color, (x, y, 1, 1))

        return (image, image.get_rect())

    def save(self, filename):
        config = self.deflate()

        with open(filename, 'w') as deflated_sprite:
            config.write(deflated_sprite)

    def deflate(self):
        config = configparser.ConfigParser(dict_type=collections.OrderedDict,
                                           empty_lines_in_values=True,
                                           strict=True)

        # Get the set of distinct pixels.
        color_map = {}
        pixels = []

        raw_pixels = rgb_triplet_generator(
            pixel_data=pygame.image.tostring(self.image, 'RGB')
        )

        # We're utilizing the generator to give us RGB triplets.
        # We need a list here becasue we'll use set() to pull out the
        # unique values, but we also need to consume the list again
        # down below, so we can't solely use a generator.
        raw_pixels = [raw_pixel for raw_pixel in raw_pixels]  # noqa: R1721

        # This gives us the unique rgb triplets in the image.
        colors = set(raw_pixels)

        config.add_section('sprite')
        config.set('sprite', 'name', self.name)

        # Generate the color key
        color_key = chr(47)
        for color in colors:
            # Characters above doublequote.
            color_key = chr(ord(color_key) + 1)
            config.add_section(color_key)

            color_map[color] = color_key

            log.debug(f'Key: {color} -> {color_key}')

            red = color[0]
            config.set(color_key, 'red', str(red))

            green = color[1]
            config.set(color_key, 'green', str(green))

            blue = color[2]
            config.set(color_key, 'blue', str(blue))

        x = 0
        row = []
        while raw_pixels:
            row.append(color_map[raw_pixels.pop(0)])
            x += 1

            if x % self.rect.width == 0:
                log.debug(f'Row: {row}')
                pixels.append(''.join(row))
                row = []
                x = 0

        log.debug(pixels)

        config.set('sprite', 'pixels', '\n'.join(pixels))

        log.debug(f'Deflated Sprite: {config}')

        return config


# This is a root class for sprites that should be singletons, like
# the MenuBar class, and the MousePointer class.
class SingletonBitmappySprite(BitmappySprite):
    __instance__ = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance__ is None:
            cls.__instance__ = object.__new__(cls)
        cls.__instance__.args = args
        cls.__instance__.kwargs = kwargs
        return cls.__instance__

    def __init__(self, x, y, width, height, name=None, groups=pygame.sprite.LayeredDirty()):
        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)


# We're making this a singleton class becasue
# pygame doesn't understand multiple cursors
# and so there is only ever 1 x/y coordinate sprite
# for the mouse at any given time.
class MousePointer(SingletonBitmappySprite):
    def __init__(self, x, y):
        super().__init__(x=x, y=y, width=1, height=1)

        self.rect.x = self.x
        self.rect.y = self.y
