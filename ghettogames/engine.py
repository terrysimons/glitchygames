#!/usr/bin/env python
# -*- coding: utf-8 -*-

import collections
import configparser
import inspect
import logging
import multiprocessing
import os
import platform

# from pygame import Color, Rect
import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

from ghettogames.color import PURPLE, BLACK

log = logging.getLogger('game.engine')
log.addHandler(logging.NullHandler())

vga_palette = [(0, 0, 0),
               (0, 0, 170),
               (0, 170, 0),
               (0, 170, 170),
               (170, 0, 0),
               (170, 0, 170),
               (170, 85, 0),
               (170, 170, 170),
               (85, 85, 85),
               (85, 85, 255),
               (85, 255, 85),
               (85, 255, 255),
               (255, 85, 85),
               (255, 85, 255),
               (255, 255, 85),
               (255, 255, 255),
               (0, 0, 0),
               (20, 20, 20),
               (32, 32, 32),
               (44, 44, 44),
               (56, 56, 56),
               (69, 69, 69),
               (81, 81, 81),
               (97, 97, 97),
               (113, 113, 113),
               (130, 130, 130),
               (146, 146, 146),
               (162, 162, 162),
               (182, 182, 182),
               (203, 203, 203),
               (227, 227, 227),
               (255, 255, 255),
               (0, 0, 255),
               (65, 0, 255),
               (125, 0, 255),
               (190, 0, 255),
               (255, 0, 255),
               (255, 0, 190),
               (255, 0, 125),
               (255, 0, 65),
               (255, 0, 0),
               (255, 65, 0),
               (255, 125, 0),
               (255, 190, 0),
               (255, 255, 0),
               (190, 255, 0),
               (125, 255, 0),
               (65, 255, 0),
               (0, 255, 0),
               (0, 255, 65),
               (0, 255, 125),
               (0, 255, 190),
               (0, 255, 255),
               (0, 190, 255),
               (0, 125, 255),
               (0, 65, 255),
               (125, 125, 255),
               (158, 125, 255),
               (190, 125, 255),
               (223, 125, 255),
               (255, 125, 255),
               (255, 125, 223),
               (255, 125, 190),
               (255, 125, 158),
               (255, 125, 125),
               (255, 158, 125),
               (255, 190, 125),
               (255, 223, 125),
               (255, 255, 125),
               (223, 255, 125),
               (190, 255, 125),
               (158, 255, 125),
               (125, 255, 125),
               (125, 255, 158),
               (125, 255, 190),
               (125, 255, 223),
               (125, 255, 255),
               (125, 223, 255),
               (125, 190, 255),
               (125, 158, 255),
               (182, 182, 255),
               (199, 182, 255),
               (219, 182, 255),
               (235, 182, 255),
               (255, 182, 255),
               (255, 182, 235),
               (255, 182, 219),
               (255, 182, 199),
               (255, 182, 182),
               (255, 199, 182),
               (255, 219, 182),
               (255, 235, 182),
               (255, 255, 182),
               (235, 255, 182),
               (219, 255, 182),
               (199, 255, 182),
               (182, 255, 182),
               (182, 255, 199),
               (182, 255, 219),
               (182, 255, 235),
               (182, 255, 255),
               (182, 235, 255),
               (182, 219, 255),
               (182, 199, 255),
               (0, 0, 113),
               (28, 0, 113),
               (56, 0, 113),
               (85, 0, 113),
               (113, 0, 113),
               (113, 0, 85),
               (113, 0, 56),
               (113, 0, 28),
               (113, 0, 0),
               (113, 28, 0),
               (113, 56, 0),
               (113, 85, 0),
               (113, 113, 0),
               (85, 113, 0),
               (56, 113, 0),
               (28, 113, 0),
               (0, 113, 0),
               (0, 113, 28),
               (0, 113, 56),
               (0, 113, 85),
               (0, 113, 113),
               (0, 85, 113),
               (0, 56, 113),
               (0, 28, 113),
               (56, 56, 113),
               (69, 56, 113),
               (85, 56, 113),
               (97, 56, 113),
               (113, 56, 113),
               (113, 56, 97),
               (113, 56, 85),
               (113, 56, 69),
               (113, 56, 56),
               (113, 69, 56),
               (113, 85, 56),
               (113, 97, 56),
               (113, 113, 56),
               (97, 113, 56),
               (85, 113, 56),
               (69, 113, 56),
               (56, 113, 56),
               (56, 113, 69),
               (56, 113, 85),
               (56, 113, 97),
               (56, 113, 113),
               (56, 97, 113),
               (56, 85, 113),
               (56, 69, 113),
               (81, 81, 113),
               (89, 81, 113),
               (97, 81, 113),
               (105, 81, 113),
               (113, 81, 113),
               (113, 81, 105),
               (113, 81, 97),
               (113, 81, 89),
               (113, 81, 81),
               (113, 89, 81),
               (113, 97, 81),
               (113, 105, 81),
               (113, 113, 81),
               (105, 113, 81),
               (97, 113, 81),
               (89, 113, 81),
               (81, 113, 81),
               (81, 113, 89),
               (81, 113, 97),
               (81, 113, 105),
               (81, 113, 113),
               (81, 105, 113),
               (81, 97, 113),
               (81, 89, 113),
               (0, 0, 65),
               (16, 0, 65),
               (32, 0, 65),
               (48, 0, 65),
               (65, 0, 65),
               (65, 0, 48),
               (65, 0, 32),
               (65, 0, 16),
               (65, 0, 0),
               (65, 16, 0),
               (65, 32, 0),
               (65, 48, 0),
               (65, 65, 0),
               (48, 65, 0),
               (32, 65, 0),
               (16, 65, 0),
               (0, 65, 0),
               (0, 65, 16),
               (0, 65, 32),
               (0, 65, 48),
               (0, 65, 65),
               (0, 48, 65),
               (0, 32, 65),
               (0, 16, 65),
               (32, 32, 65),
               (40, 32, 65),
               (48, 32, 65),
               (56, 32, 65),
               (65, 32, 65),
               (65, 32, 56),
               (65, 32, 48),
               (65, 32, 40),
               (65, 32, 32),
               (65, 40, 32),
               (65, 48, 32),
               (65, 56, 32),
               (65, 65, 32),
               (56, 65, 32),
               (48, 65, 32),
               (40, 65, 32),
               (32, 65, 32),
               (32, 65, 40),
               (32, 65, 48),
               (32, 65, 56),
               (32, 65, 65),
               (32, 56, 65),
               (32, 48, 65),
               (32, 40, 65),
               (44, 44, 65),
               (48, 44, 65),
               (52, 44, 65),
               (60, 44, 65),
               (65, 44, 65),
               (65, 44, 60),
               (65, 44, 52),
               (65, 44, 48),
               (65, 44, 44),
               (65, 48, 44),
               (65, 52, 44),
               (65, 60, 44),
               (65, 65, 44),
               (60, 65, 44),
               (52, 65, 44),
               (48, 65, 44),
               (44, 65, 44),
               (44, 65, 48),
               (44, 65, 52),
               (44, 65, 60),
               (44, 65, 65),
               (44, 60, 65),
               (44, 52, 65),
               (44, 48, 65),
               (0, 0, 0),
               (0, 0, 0),
               (0, 0, 0),
               (0, 0, 0),
               (0, 0, 0),
               (0, 0, 0),
               (0, 0, 0),
               (0, 0, 0)]


def indexed_rgb_triplet_generator(pixel_data):
    try:
        for datum in pixel_data:
            yield datum[0]
    except StopIteration:
        pass


def rgb_555_triplet_generator(pixel_data):
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
    iterator = iter(pixel_data)

    try:
        while True:
            # range(3) gives us 3 at a time, so r, g, b.
            yield tuple([next(iterator) for i in range(3)])
    except StopIteration:
        pass


def image_from_pixels(pixels, width, height):
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
    pixels = rgb_triplet_generator(
        pixel_data=pixel_data,
    )

    pixels = [pixel for pixel in pixels]

    return pixels


def pixels_from_path(path):
    with open(path, 'rb') as fh:
        pixel_data = fh.read()

    pixels = pixels_from_data(
        pixel_data=pixel_data
    )

    return pixels


class ResourceManager(object):
    __instances__ = {}

    def __new__(cls, *args, **kwargs):
        if cls not in cls.__instances__:
            cls.__instances__[cls] = object.__new__(cls)
            log.debug(f'Created Resource Manager: {cls}')
            cls.__instances__[cls].args = args
            cls.__instances__[cls].kwargs = kwargs

        return cls.__instances__[cls]

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.proxies = None

    # A resource manager will generally pass all requests through
    # to its proxy object, however, for certain types of resources
    # such as joysticks, the subclass will manage things itself.
    #
    # Doing things this way reduces code footprint, and allows
    # maximum flexibility when needed at the expense of a bit
    # of over abstracting.
    def __getattr__(self, attr):
        # Try each proxy in turn
        for proxy in self.proxies:
            try:
                return getattr(proxy, attr)
            except AttributeError:
                log.error(f'No proxies for {type(self)}.{attr}')


class EventManager(ResourceManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        class EventProxy(object):
            def __init__(self, *args, **kwargs):
                super().__init__()
                # No proxies for the root class.
                self.proxies = []

                # This is used for leave objects which
                # don't have their own proxies.
                #
                # Subclassed managers that set their own proxy
                # will not have this.
                self.event_source = kwargs.get('event_source', None)

            def unhandled_event(self, *args, **kwargs):
                # inspect.stack()[1] is the call frame above us, so this should be reasonable.
                event_handler = inspect.stack()[1].function

                event = kwargs.get('event')

                log.debug(f'Unhandled Event {event_handler}: {self.event_source}->{event}')

            def unimplemented_event(self, *args, **kwargs):
                # inspect.stack()[1] is the call frame above us, so this should be reasonable.
                event_handler = inspect.stack()[1].function

                event = kwargs.get('event')

                log.debug(f'Unimplemented Event {event_handler}: {self.event_source}->{event}')

                raise Exception(f'Add a stub for {event_handler}(self, *args, **kwargs) '
                                'to {type(self)}.')

            def on_active_event(self, event):
                # ACTIVEEVENT      gain, state
                self.unhandled_event(event=event)

            def on_mouse_motion_event(self, event):
                # MOUSEMOTION      pos, rel, buttons
                self.unhandled_event(event=event)

            def on_mouse_button_up_event(self, event):
                # MOUSEBUTTONUP    pos, button
                self.unhandled_event(event=event)

            def on_left_mouse_button_up_event(self, event):
                # Left Mouse Button Up pos, button
                self.unhandled_event(event=event)

            def on_middle_mouse_button_up_event(self, event):
                # Middle Mouse Button Up pos, button
                self.unhandled_event(event=event)

            def on_right_mouse_button_up_event(self, event):
                # Right Mouse Button Up pos, button
                self.unhandled_event(event=event)

            def on_mouse_button_down_event(self, event):
                # MOUSEBUTTONDOWN  pos, button
                self.unhandled_event(event=event)

            def on_left_mouse_button_down_event(self, event):
                # Left Mouse Button Down pos, button
                self.unhandled_event(event=event)

            def on_middle_mouse_button_down_event(self, event):
                # Middle Mouse Button Down pos, button
                self.unhandled_event(event=event)

            def on_right_mouse_button_down_event(self, event):
                # Right Mouse Button Down pos, button
                self.unhandled_event(event=event)

            def on_mouse_scroll_down_event(self, event):
                # This is a synthesized event.
                self.unhandled_event(event=event)

            def on_mouse_scroll_up_event(self, event):
                # This is a synthesized event.
                self.unhandled_event(event=event)

            def on_key_up_event(self, event):
                # KEYUP            key, mod
                self.unhandled_event(event=event)

            def on_key_down_event(self, event):
                # KEYDOWN            key, mod
                self.unhandled_event(event=event)

            def on_key_chord_down_event(self, event, trigger):
                # This is a synthesized event.
                self.unhandled_event(event=event)

            def on_key_chord_up_event(self, event, trigger):
                # This is a synthesized event.
                self.unhandled_event(event=event)

            def __getattr__(self, attr):
                return self.unimplemented_event

        self.proxies = [EventProxy(event_source=self)]
        self.game = kwargs.get('game', None)

class FontManager(ResourceManager):
    DEFAULT_FONT_SETTINGS = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Register pygame.freetype
        pygame.freetype.init()
        pygame.font.init()

        self.font = kwargs.get('font', pygame.freetype.get_default_font())
        self.font_size = kwargs.get('font_size', 12)
        self.font_bold = kwargs.get('font_bold', False)
        self.font_italic = kwargs.get('font_italic', False)
        self.font_antialias = kwargs.get('font_antialias', False)
        self.font_dpi = kwargs.get('font_dpi', 72)
        self.ready = True

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
        #pygame.ftfont.init()

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Font Options')

        group.add_argument('--font',
                           default=None)
        group.add_argument('--font-size',
                           type=int,
                           default=16)
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

class MusicManager(ResourceManager):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Music Options')  # noqa: W0612

        return parser

class SoundManager(ResourceManager):
    __instance__ = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance__ is None:
            cls.__instance__ = object.__new__(cls)
        cls.__instance__.args = args
        cls.__instance__.kwargs = kwargs
        return cls.__instance__

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Set the mixer pre-init settings
        pygame.mixer.pre_init(22050, -16, 2, 1024)

        # Sound Stuff
        # pygame.mixer.get_init() -> (frequency, format, channels)
        (frequency, format, channels) = pygame.mixer.get_init()
        log.info('Mixer Settings:')
        log.info(f'Frequency: {frequency}, Format: {format}, Channels: {channels}')
        self.ready = True

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Sound Mixer Options')  # noqa: W0612

        return parser

class KeyboardManager(ResourceManager):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.game = kwargs.get('game', None)

        class KeyboardProxy(ResourceManager):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.keys = {}

                self.game = kwargs.get('game', None)
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

        self.proxies = [KeyboardProxy(game=self.game)]

class MouseManager(ResourceManager):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.game = kwargs.get('game', None)

        class MouseProxy(ResourceManager):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.mouse_state = {}
                self.mouse_dragging = False
                self.current_focus = None
                self.previous_focus = None
                self.focus_locked = False

                self.game = kwargs.get('game', None)
                self.proxies = [self.game, pygame.mouse]

            def on_mouse_motion_event(self, event):
                self.mouse_state[event.type] = event

                self.game.on_mouse_motion_event(event)

                # Figure out which item was clicked.
                mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

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
                        self.on_mouse_drag_down_event(event, trigger)
                        self.mouse_dragging = True

            def on_mouse_drag_down_event(self, event, trigger):
                self.game.on_mouse_drag_down_event(event, trigger)

                if self.focus_locked:
                    if self.current_focus:
                        self.current_focus.on_mouse_drag_down_event(event, trigger)
                    elif self.previous_focus:
                        self.previous_focus.on_mouse_drag_down_event(event, trigger)

                if trigger.button == 1:
                    self.on_left_mouse_drag_down_event(event, trigger)
                if trigger.button == 2:
                    self.on_middle_mouse_drag_down_event(event, trigger)
                if trigger.button == 3:
                    self.on_right_mouse_drag_down_event(event, trigger)
                if trigger.button == 4:
                    # This doesn't really make sense.
                    pass
                if trigger.button == 5:
                    # This doesn't really make sense.
                    pass

            def on_left_mouse_drag_down_event(self, event, trigger):
                self.game.on_left_mouse_drag_down_event(event, trigger)

                if self.focus_locked:
                    if self.current_focus:
                        self.current_focus.on_left_mouse_drag_down_event(event, trigger)
                    elif self.previous_focus:
                        self.previous_focus.on_left_mouse_drag_down_event(event, trigger)

            def on_left_mouse_drag_up_event(self, event, trigger):
                self.game.on_left_mouse_drag_up_event(event, trigger)

                if self.focus_locked:
                    if self.current_focus:
                        self.current_focus.on_left_mouse_drag_up_event(event, trigger)
                    elif self.previous_focus:
                        self.previous_focus.on_left_mouse_drag_up_event(event, trigger)

            def on_middle_mouse_drag_down_event(self, event, trigger):
                self.game.on_middle_mouse_drag_down_event(event, trigger)

                if self.focus_locked:
                    if self.current_focus:
                        self.current_focus.on_middle_mouse_drag_down_event(event, trigger)
                    elif self.previous_focus:
                        self.previous_focus.on_middle_mouse_drag_down_event(event, trigger)

            def on_middle_mouse_drag_up_event(self, event, trigger):
                self.game.on_middle_mouse_drag_up_event(event, trigger)

                if self.focus_locked:
                    if self.current_focus:
                        self.current_focus.on_middle_mouse_drag_up_event(event, trigger)
                    elif self.previous_focus:
                        self.previous_focus.on_middle_mouse_drag_up_event(event, trigger)

            def on_right_mouse_drag_down_event(self, event, trigger):
                self.game.on_right_mouse_drag_down_event(event, trigger)

                if self.focus_locked:
                    if self.current_focus:
                        self.current_focus.on_right_mouse_drag_down_event(event, trigger)
                    elif self.previous_focus:
                        self.previous_focus.on_right_mouse_drag_down_event(event, trigger)

            def on_right_mouse_drag_up_event(self, event, trigger):
                self.game.on_right_mouse_drag_up_event(event, trigger)

                if self.focus_locked:
                    if self.current_focus:
                        self.current_focus.on_right_mouse_drag_up_event(event, trigger)
                    elif self.previous_focus:
                        self.previous_focus.on_right_mouse_drag_up_event(event, trigger)

            def on_mouse_drag_up_event(self, event):
                log.debug(f'{type(self)}: Mouse Drag Up: {event}')
                mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

                collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

                for sprite in collided_sprites:
                    sprite.on_mouse_drag_up_event(event)

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
                    # It doesn't really make sense to hook this
                    pass
                if event.button == 5:
                    # It doesn't really make sense to hook this
                    pass

                if self.mouse_dragging:
                    self.game.on_mouse_drag_up_event(event)
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

        self.proxies = [MouseProxy(game=self.game)]

class JoystickManager(ResourceManager):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.joysticks = []

        class JoystickProxy(ResourceManager):

            def __init__(self, id, **kwargs):
                super().__init__()
                self._id = id
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

                self.game = kwargs.get('game', None)
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
                joystick_info.append(f'\tJoystick Id: {self.get_id()}')
                joystick_info.append(f'\tJoystick Inited: {self.get_init()}')
                joystick_info.append(f'\tJoystick Axis Count: {self.get_numaxes()}')
                joystick_info.append(f'\tJoystick Trackball Count: {self.get_numballs()}')
                joystick_info.append(f'\tJoystick Button Count: {self.get_numbuttons()}')
                joystick_info.append(f'\tJoystick Hat Count: {self.get_numhats()}')
                return '\n'.join(joystick_info)

            def __repr__(self):
                return repr(self.joystick)

        # This must be called before other joystick methods,
        # and is safe to call more than once.
        pygame.joystick.init()

        log.info(f'Joystick Module Inited: {pygame.joystick.get_init()}')

        # Joystick Setup
        log.info(f'Joystick Count: {pygame.joystick.get_count()}')
        joysticks = [pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())]

        for i, joystick in enumerate(joysticks):
            joystick.init()
            joystick_proxy = JoystickProxy(id=joystick.get_id(), game=self.game)
            self.joysticks.append(joystick_proxy)

            # The joystick proxy overrides the joystick object
            log.info(joystick_proxy)

        self.ready = True

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.game = kwargs.get('game', None)

        class GameProxy(ResourceManager):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.game = kwargs.get('game')
                self.proxies = [self.game]

        self.proxies = [GameProxy(game=self.game)]

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Game Options')  # noqa: W0612

        return parser

class GameEngine(EventManager):
    NAME = "Boilerplate Adventures"
    VERSION = "1.0"
    FPS = 0
    OPTIONS = None
    MOUSE_EVENTS = [pygame.MOUSEMOTION,
                    pygame.MOUSEBUTTONUP,
                    pygame.MOUSEBUTTONDOWN]

    KEYBOARD_EVENTS = [pygame.KEYDOWN,
                       pygame.KEYUP]

    JOYSTICK_EVENTS = [pygame.JOYAXISMOTION,
                       pygame.JOYBALLMOTION,
                       pygame.JOYHATMOTION,
                       pygame.JOYBUTTONUP,
                       pygame.JOYBUTTONDOWN]

    FPSEVENT = pygame.USEREVENT + 1
    GAMEEVENT = pygame.USEREVENT + 2
    MENUEVENT = pygame.USEREVENT + 3
    GAME_EVENTS = [FPSEVENT,
                   GAMEEVENT,
                   MENUEVENT,
                   pygame.USEREVENT,
                   pygame.QUIT,
                   pygame.ACTIVEEVENT,
                   pygame.VIDEORESIZE,
                   pygame.VIDEOEXPOSE,
                   pygame.SYSWMEVENT]

    def __init__(self, options=dict()):
        # Persist this game's options.
        GameEngine.OPTIONS = options

        # Add a copy of ourselves to this singleton's options.
        #
        # This makes getting a handle to the running game easy.
        GameEngine.OPTIONS['game'] = self

        super().__init__(**options)

        # A bit of black magic.
        self.proxies = [self]

        # General stuff.
        self.cpu_count = multiprocessing.cpu_count()
        self.system = platform.system()
        self.machine = platform.machine()
        self.platform = platform.platform(aliased=0, terse=0)
        self.platform_terse = platform.platform(aliased=0, terse=1)
        self.processor = platform.processor()
        self.release = platform.release()

        log.info(f'CPU Count: {self.cpu_count}')
        log.info(f'System: {self.system}')
        log.info(f'Machine: {self.machine}')
        log.info(f'Platform: {self.platform}')
        log.info(f'Platform (Terse): {self.platform_terse}')
        log.info(f'Processor: {self.processor}')
        log.info(f'Release: {self.release}')

        # Pygame stuff.
        pygame.register_quit(self.quit)
        self.fps = options.get('fps', 0)
        self.update_type = options.get('update_type')
        self.use_gfxdraw = options.get('use_gfxdraw')
        self.video_driver = options.get('video_driver')
        self.windowed = options.get('windowed')
        self.desired_resolution = options.get('resolution')
        self.fps_refresh_rate = options.get('fps_refresh_rate')

        log.info(f'Game Title: {type(self).NAME}')
        log.info(f'Game Version: {type(self).VERSION}')

        # Initialize all of the Pygame modules.
        self.init_pass, self.init_fail = pygame.init()
        log.debug(f'Successfully loaded {self.init_pass} modules '
                  'and failed loading {self.init_fail} modules.')

        # Enable fast events for multithreaded applications
        pygame.fastevent.init()

        self.clock = pygame.time.Clock()

        self.font_manager = FontManager(**GameEngine.OPTIONS)
        self.sound_manager = SoundManager(**GameEngine.OPTIONS)
        self.music_manager = MusicManager(**GameEngine.OPTIONS)
        self.joystick_manager = JoystickManager(**GameEngine.OPTIONS)
        self.keyboard_manager = KeyboardManager(**GameEngine.OPTIONS)
        self.mouse_manager = MouseManager(**GameEngine.OPTIONS)
        self.game_manager = GameManager(**GameEngine.OPTIONS)
        self.registered_events = {}

        # Get count of joysticks
        if self.joystick_manager:
            self.joysticks = self.joystick_manager.joysticks
            self.joystick_count = len(self.joysticks)

        # Resolution initialization.
        # Convert our resolution to a tuple
        (self.desired_width, self.desired_height) = self.desired_resolution.split('x')
        if self.windowed:
            self.mode_flags = 0
        else:
            self.mode_flags = pygame.FULLSCREEN

            # For Ubuntu 19.04, we can't reset the original res
            # so let's just let the system figure it out.
            if self.system == 'Linux':
                if not 'arm' in self.machine:
                    log.info('Ignoring full screen resolution change on Linux.')
                    self.desired_width = 0
                    self.desired_height = 0
                else:
                    # RPi Hack
                    #
                    # The Raspberry Pi screen exposes
                    # 2 resolutions, but only one works properly
                    self.desired_width = 800
                    self.desired_height = 480
        self.color_depth = 0
        self.desired_resolution = (int(self.desired_width), int(self.desired_height))

        # Event Handling Shortcuts
        self.mouse_events = [pygame.MOUSEMOTION,
                             pygame.MOUSEBUTTONDOWN,
                             pygame.MOUSEBUTTONUP]

        self.joystick_events = [pygame.JOYAXISMOTION,
                                pygame.JOYBALLMOTION,
                                pygame.JOYHATMOTION,
                                pygame.JOYBUTTONUP,
                                pygame.JOYBUTTONDOWN]

        self.keyboard_events = [pygame.KEYDOWN,
                                pygame.KEYUP]

        # Display some configuration information.
        log.info(f'SDL Version: {pygame.get_sdl_version()}')
        log.info(f'SDL Byte Order: {pygame.get_sdl_byteorder()}')

        # Set up a display mode.
        # Note: pygame.display.init() isn't necessary here
        # because we've already called pygame.init() which
        # initializes all available modules.
        #
        # Let's do a sanity check and make sure we're initialized.
        log.info(f'Display inited: {pygame.display.get_init()}')

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

        # Let's try to set a resolution to the most compatible for
        # the system.  If we don't provide any parameters, we'll get
        # a reasonble default, but you should consider whether that's
        # a good idea for your particular application.
        #
        # We'll cover how to set modes in  different tutorial.
        #
        # This tutorial aims for maximum compatibility.
        #
        # There are various caveats for hardware accelerated blitting
        # that make it undesirable in a lot of cases, so we'll just use
        # software.
        self.display_info = pygame.display.Info()
        self.initial_resolution = (self.display_info.current_w,
                                   self.display_info.current_h)

        # Dump a bit more info about the configured mode.
        log.info(f'Display Driver: {pygame.display.get_driver()}')
        log.info(f'Display Info: {self.display_info}')
        log.info(f'Initial Resolution: {self.initial_resolution}')
        log.info(f'8-bit Modes: {pygame.display.list_modes(8)}')
        log.info(f'16-bit Modes: {pygame.display.list_modes(16)}')
        log.info(f'24-bit Modes: {pygame.display.list_modes(24)}')
        log.info(f'32-bit Modes: {pygame.display.list_modes(32)}')
        log.info(f'Best Color Depth: {pygame.display.mode_ok(self.initial_resolution), self.mode_flags} ({self.mode_flags})')
        log.info(f'Window Manager Info: {pygame.display.get_wm_info()}')
        log.info(f'Platform Timer Resolution: {pygame.TIMER_RESOLUTION}')

        # Cursor setup.
        # Cursor width/height must be a multiple of 8
        self.cursor = [
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

        self.cursor_width = len(self.cursor[0])
        self.cursor_height = len(self.cursor)
        self.cursor_data = None
        self.cursor_mask = None
        self.cursor_black = '.'
        self.cursor_white = 'X'
        self.cursor_xor = 'o'

        # Compile and set our cursor for drawing.
        self.update_cursor()

        # Set the screen update type.
        if self.update_type == 'update':
            self.display_update = pygame.display.update
        elif self.update_type == 'flip':
            self.display_update = pygame.display.flip
        else:
            log.error('Screen update type was neither "update" nor "flip".')

        # If a video driver was set, use it.
        if self.video_driver:
            os.environ['SDL_VIDEODRIVER'] = self.video_driver
        else:
            self.video_driver = os.environ.get('SDL_VIDEODRIVER', None)

        if self.video_driver:
            log.info(f'SDL_VIDEODRIVER == {os.environ["SDL_VIDEODRIVER"]}')

        # The Pygame documentation recommends against using hardware accelerated blitting.
        #
        # Note that you can also get the screen with pygame.display.get_surface()
        self.screen = pygame.display.set_mode(self.desired_resolution,
                                              self.mode_flags,
                                              self.color_depth)

        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

    def update_cursor(self):
        # Compile our cursor so we can draw it to the screen.
        self.cursor_data, self.cursor_mask = pygame.cursors.compile(self.cursor,
                                                                    black=self.cursor_black,
                                                                    white=self.cursor_white,
                                                                    xor=self.cursor_xor)

        # Now set the cursor as the active cursor.
        pygame.mouse.set_cursor((self.cursor_width, self.cursor_height),
                                (0, 0),
                                self.cursor_data,
                                self.cursor_mask)

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
                           default=False)
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
        windows_videodriver_choices = ['windib', 'directx']

        linux_videodriver_choices = ['x11',
                                     'dga',
                                     'fbcon',
                                     'directfb',
                                     'ggi',
                                     'vgl',
                                     'svgalib',
                                     'aalib']

        mac_videodriver_choices = []

        group.add_argument('--video-driver',
                           default=None,
                           choices=linux_videodriver_choices)

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

    def quit(self):
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

    def load_resources(self):
        log.info('Implement load_resource() in your subclass.')

    def process_events(self):
        # To use events in a different thread, use the fastevent package from pygame.
        # You can create your own new events with the pygame.event.Event() function.
        for event in pygame.fastevent.get():
            if event.type in self.GAME_EVENTS:
                self.process_game_event(event)
            elif event.type in self.JOYSTICK_EVENTS:
                self.process_joystick_event(event)
            elif event.type in self.MOUSE_EVENTS:
                self.process_mouse_event(event)
            elif event.type in self.KEYBOARD_EVENTS:
                self.process_keyboard_event(event)
            else:
                # This will catch any unimplemented event types that we see.
                log.error(f'Unknown Event Type: {event.type}: {event}')

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

    def post_game_event(self, event_subtype, event_data):
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

    #def on_key_up_event(self, event):
    #    super().on_key_up_event(event)
        # Wire up quit by default for escape and q.
        #
        # If a game implements on_key_up_event themselves
        # they'll have to map their quit keys or call super().on_key_up_event()
    #    if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
    #        log.info('User requested quit.')
    #        self.quit()

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
    def __init__(self):
        super().__init__()
        # This will resolve to the class name of any subclass.
        self.name = type(self)
        self.background_color = BLACK
        self.next = self
        self.rects = None

        # http://n0nick.github.io/blog/2012/06/03/quick-dirty-using-pygames-dirtysprite-layered/
        self.all_sprites = pygame.sprite.LayeredDirty()

        # Initial screen state.
        self.screen = pygame.display.get_surface()
        self.background = pygame.Surface(self.screen.get_size())
        self.background.convert()
        self.background.fill(self.background_color)

        self.all_sprites.clear(self.screen, self.background)

        #self.proxies = [EventManager()]

    def update(self):
        self.rects = self.all_sprites.draw(self.screen)

    def render(self, screen):
        self.all_sprites.update()

    def switch_to_scene(self, next_scene):
        self.next = next_scene

    def terminate(self):
        self.switch_to_scene(None)

    #def on_axis_motion_event(self, event):
        # JOYAXISMOTION    joy, axis, value
    #    log.debug(f'{type(self)}: {event}')

    #def on_button_down_event(self, event):
    #    # JOYBUTTONDOWN    joy, button
    #    log.debug(f'{}: {event}')

    #def on_button_up_event(self, event):
    #    # JOYBUTTONUP      joy, button
    #    log.debug(f'{self.root_scene}: {event}')

    #def on_hat_motion_event(self, event):
    #    # JOYHATMOTION     joy, hat, value
    #    log.debug(f'{self.root_scene}: {event}')

    #def on_ball_motion_event(self, event):
    #    # JOYBALLMOTION    joy, ball, rel
    #    log.debug(f'{type(self)}: {event}')

    #def on_mouse_motion_event(self, event):
    #    # MOUSEMOTION      pos, rel, buttons
    #    log.debug(f'{self.root_scene}: {event}')

    def on_mouse_drag_down_event(self, event, trigger):
        log.debug(f'{type(self)}: Mouse Drag Down: {event} {trigger}')
        mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in collided_sprites:
            sprite.on_mouse_drag_down_event(event, trigger)

    def on_left_mouse_drag_down_event(self, event, trigger):
        #log.info(f'{self.root_scene}: Left Mouse Drag Down: {event} {trigger}')

        mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in collided_sprites:
            sprite.on_left_mouse_drag_down_event(event, trigger)

    def on_left_mouse_drag_up_event(self, event, trigger):
        log.info(f'{type(self)}: Left Mouse Drag Up: {event} {trigger}')

        mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in collided_sprites:
            sprite.on_left_mouse_drag_up_event(event)

    def on_middle_mouse_drag_down_event(self, event, trigger):
        log.info(f'{type(self)}: Middle Mouse Drag Down: {event} {trigger}')

        mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_drag_down_event(event, trigger)

    def on_middle_mouse_drag_up_event(self, event, trigger):
        log.info(f'{type(self)}: Middle Mouse Drag Up: {event} {trigger}')

        mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_drag_up_event(event)

    def on_right_mouse_drag_down_event(self, event, trigger):
        log.info(f'{type(self)}: Right Mouse Drag Down: {event} {trigger}')

        mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in collided_sprites:
            sprite.on_right_mouse_drag_up_event(event, trigger)

    def on_right_mouse_drag_up_event(self, event, trigger):
        log.info(f'{type(self)}: Right Mouse Drag Up: {event} {trigger}')

        mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in collided_sprites:
            sprite.on_right_mouse_drag_up_event(event)

    def on_mouse_drag_up_event(self, event):
        log.debug(f'{type(self)}: Mouse Drag Up: {event}')
        mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in collided_sprites:
            sprite.on_mouse_drag_up_event(event)

    #def on_mouse_button_up_event(self, event):
    #    # MOUSEBUTTONUP    pos, button
    #    log.debug(f'{self.root_scene}: {event}')

    def on_left_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        log.debug(f'{type(self)}: Left Mouse Button Up Event: {event}')
        self.on_mouse_button_up_event(event)

        mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        if not collided_sprites:
            log.info('No match.')

        for sprite in collided_sprites:
            sprite.on_left_mouse_button_up_event(event)

    #def on_middle_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
    #    log.debug(f'{self.root_scene}: Middle Mouse Button Up Event: {event}')

    def on_right_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        log.info(f'{type(self)}: Right Mouse Button Up Event: {event}')
        self.on_mouse_button_up_event(event)

        mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        if not collided_sprites:
            log.info('No match.')

        for sprite in collided_sprites:
            sprite.on_right_mouse_button_up_event(event)

    def on_left_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        log.debug(f'{type(self)}: Left Mouse Button Down Event: {event}')

        mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        if not collided_sprites:
            log.info('No match.')

        for sprite in collided_sprites:
            sprite.on_left_mouse_button_down_event(event)

    def on_right_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        log.info(f'{type(self)}: Right Mouse Button Down Event: {event}')
        self.on_mouse_button_down_event(event)

        mouse = MouseSprite(x=event.pos[0], y=event.pos[1], width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        if not collided_sprites:
            log.info('No match.')

        for sprite in collided_sprites:
            sprite.on_right_mouse_button_down_event(event)

    def on_quit_event(self, event):
        # QUIT             none
        log.debug(f'{type(self)}: {event}')
        self.terminate()

    def on_fps_event(self, event):
        # FPSEVENT is pygame.USEREVENT + 1
        log.info(f'{type(self)}: {GameEngine.FPS}')

class RootSprite(pygame.sprite.DirtySprite):
    """
    This is a convenience class for handling all of the common sprite behaviors.
    """
    USE_GFXDRAW = False

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.name = type(self)
        self.x = kwargs.get('x', 0)
        self.y = kwargs.get('y', 0)
        self.width = int(kwargs.get('width', 0))
        self.height = int(kwargs.get('height', 0))
        self.proxies = [self]

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

        # Cause the sprite to update itself when it comes into existence.
        self.update()

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

    def on_fps_event(self, event):
        # FPSEVENT is pygame.USEREVENT + 1
        log.debug(f'{type(self)}: {GameEngine.FPS}')

    def __str__(self):
        return f'{type(self)} "{self.name}" ({repr(self)})'

class BitmappySprite(RootSprite):
    DEBUG = False

    def __init__(self, *args, filename=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.image = None
        self.rect = None
        self.name = kwargs.get('name', 'Untitled')
        self.filename = filename
        self.width = kwargs.get('width', 0)
        self.height = kwargs.get('height', 0)

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
        self.rect.x = kwargs.get('x', 0)
        self.rect.y = kwargs.get('y', 0)

    def load(self, filename):
        """
        """
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

    def inflate(self, width, height, pixels, color_map):
        """
        """
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
        """
        """
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
        raw_pixels = [raw_pixel for raw_pixel in raw_pixels]

        # This gives us the unique rgb triplets in the image.
        colors = set(raw_pixels)

        config.add_section('sprite')
        config.set('sprite', 'name', self.name)

        # Generate the color key
        color_key = chr(47)
        for i, color in enumerate(colors):
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
# the MenuBar class, and the MouseSprite class.
class SingletonBitmappySprite(BitmappySprite):
    __instance__ = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance__ is None:
            cls.__instance__ = object.__new__(cls)
        cls.__instance__.args = args
        cls.__instance__.kwargs = kwargs
        return cls.__instance__

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# We're making this a singleton class becasue
# pygame doesn't understand multiple cursors
# and so there is only ever 1 x/y coordinate sprite
# for the mouse at any given time.
class MouseSprite(SingletonBitmappySprite):
    def __init__(self, *args, **kwargs):
        self.x = kwargs.get('x')
        self.y = kwargs.get('y')

        super().__init__(*args, **kwargs)

        self.rect.x = self.x
        self.rect.y = self.y
