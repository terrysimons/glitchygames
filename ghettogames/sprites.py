import collections
import configparser
import logging

import pygame

from ghettogames.events import MouseEvents

log = logging.getLogger('game.sprites')
log.addHandler(logging.NullHandler())


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
