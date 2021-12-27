import logging
import time

import pygame

from ghettogames.color import BLACK
from ghettogames.events import EventInterface, EventManager
from ghettogames.sprites import MousePointer

from ghettogames.events import FPSEVENT

LOG = logging.getLogger('game.scenes')
LOG.addHandler(logging.NullHandler())


class SceneInterface:
    def switch_to_scene(self, next_scene):
        pass

    def terminate(self):
        pass


class SceneManager(SceneInterface, EventManager):
    log = LOG
    OPTIONS = {}

    def __init__(self):
        super().__init__()

        # Scene manager terminates on self.next_scene = None
        self.screen = pygame.display.get_surface()
        self.update_type = 'update'
        self.fps_refresh_rate = 1000
        self.fps = 5
        self._game_engine = None
        self.active_scene = None
        self.next_scene = self.active_scene
        self.previous_scene = self.active_scene
        self.quit_requested = False

        self.clock = pygame.time.Clock()

    @property
    def game_engine(self):
        return self._game_engine

    @game_engine.setter
    def game_engine(self, new_engine):
        self._game_engine = new_engine
        if self._game_engine:
            self.OPTIONS = self._game_engine.OPTIONS
            self.update_type = self.OPTIONS['update_type']
            self.fps_refresh_rate = self.OPTIONS['fps_refresh_rate']
            self.fps = self.OPTIONS.get('fps', 1)
            self.log.info(f'Screen update type: {self.update_type}')
            self.log.info(f'FPS Refresh Rate: {self.fps_refresh_rate}')
            self.log.info(f'Per-scene FPS: {self.fps}')

    # This enables collided_sprites in sprites.py, since SceneManager is
    # not a scene, but is the entry point for event proxies.
    @property
    def all_sprites(self):
        if self.active_scene:
            return self.active_scene.all_sprites

    def switch_to_scene(self, next_scene):
        if next_scene != self.active_scene:
            self.log.info(
                f'Switching to scene "{next_scene}" '
                f'from scene "{self.active_scene}"'
            )

            self.active_scene = next_scene

            if self.active_scene:
                pygame.display.set_caption(
                    f'{self.active_scene.NAME} v{self.active_scene.VERSION}',
                    f'{self.active_scene.NAME} v{self.active_scene.VERSION}'
                )

                self.active_scene.load_resources()

                # Infinite refresh is the default; override it if FPS was configured
                # on the command line, unless the active scene has specific FPS requirements
                if self.fps > 0 and self.active_scene.fps == 0:
                    self.active_scene.fps = self.fps

                self.log.info(
                    f'Rendering Scene "{self.active_scene.NAME}({type(self.active_scene)})"'
                    f' at {self.active_scene.fps} FPS'
                )

                # This controls how events are marshalled
                self.proxies = [self, self.active_scene]

                # Per-scene FPS configurability
                self.fps = self.active_scene.fps

    def start(self):
        start_time = time.perf_counter()
        current_time = start_time

        while self.active_scene is not None and self.quit_requested == False:
            self.active_scene.update()

            self.active_scene.render(self.screen)

            self.clock.tick(self.fps)

            if self.update_type == 'update':
                pygame.display.update(self.active_scene.rects)
            elif self.update_type == 'flip':
                pygame.display.flip()

            if (current_time - start_time) * 1000 >= self.OPTIONS['fps_refresh_rate']:
                pygame.event.post(
                    pygame.event.Event(FPSEVENT, {'fps': self.clock.get_fps()})
                )

                start_time = current_time

            self.switch_to_scene(self.active_scene.next_scene)

            self.game_engine.process_events()

            current_time = time.perf_counter()

        self.log.info(f'Game Quitting: Active Scene: {self.active_scene}, Quit Requested: {self.quit_requested}')
        self.terminate()

    def terminate(self):
        self.switch_to_scene(None)

    def quit(self):  # noqa: R0201
        # put a quit event in the event queue.
        self.log.info('POSTING QUIT EVENT')
        pygame.event.post(
            pygame.event.Event(pygame.QUIT, {})
        )

    def on_quit_event(self, event):
        # QUIT             none
        self.quit_requested = True

    def on_fps_event(self, event):
        # FPSEVENT is pygame.USEREVENT + 1
        if self.active_scene:
            self.active_scene.on_fps_event(event)

    def on_game_event(self, event):
        # GAMEEVENT is pygame.USEREVENT + 2
        # Call the event callback if it's registered.
        try:
            self.game_engine.registered_events[event.subtype](event)
        except KeyError:
            self.log.error(
                f'Unregistered Event: {event} '
                '(call self.register_game_event(<event subtype>, <event data>))'
            )

    # If the game hasn't hooked a call, we should check if the scene manager has.
    #
    # This will allow scenes to get pygame events directly, but we can still
    # hook those events in this engine, or in the subclassed game object, too.
    #
    # This allows maximum flexibility of event processing, with low overhead
    # at the expense of a slight layer violation.
    def __getattr__(self, attr):
        # Attempt to proxy the call to the active scene.
        if (attr.startswith('on_') and attr.endswith('_event')):
            try:
                # Pass it to the active scene for handling
                return getattr(self.active_scene, attr)
            except AttributeError:
                # Pass it to the game engine for suppression
                return getattr(self.game_engine, attr)
        else:
            raise AttributeError(f"'{type(self)}' object has no attribute '{attr}'")


class Scene(SceneInterface, EventInterface):
    """
    Scene object base class.

    Subclass this to properly receive on_*_event() messages automatically.
    """
    log = LOG
    FPS = 0
    NAME = 'Unnamed Scene'
    VERSION = '0.0'

    def __init__(self, options=None, groups=pygame.sprite.LayeredDirty()):
        super().__init__()

        # Since SceneManager is a singleton, this will ensure that
        # any non-active scene which gets initialized will simply
        # get a copy of the scene manager, rather than overwriting
        # the active scene.
        #
        # This helps us keep the upper layers clean by not requiring
        # new scenes to care about the SceneManager when being
        # instantiated.
        self.fps = 0
        self.options = options
        self.scene_manager = SceneManager()
        self.name = type(self)
        self._background_color = None
        self.next_scene = self
        self.rects = None
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        # http://n0nick.github.io/blog/2012/06/03/quick-dirty-using-pygames-dirtysprite-layered/
        self.all_sprites = groups

        # Initial screen state.

        self.screen = pygame.display.get_surface()
        self.background = pygame.Surface(self.screen.get_size())
        self.background.convert()
        self.background_color = BLACK

        # I don't think this will work since init() is called first.
        # for group in groups:
        #    for sprite in self.all_sprites:
        #        group.add(sprite)

    @property
    def background_color(self):
        return self._background_color

    @background_color.setter
    def background_color(self, new_color):
        self._background_color = new_color
        self.background.fill(self.background_color)
        self.all_sprites.clear(self.screen, self.background)

    def update(self):
        # Hack to enable compound sprites to manage their own subsprites dirty states
        #
        # Ideally we'd just make dirty a property with a setter and getter on each
        # sprite object, but that doesn't work for some reason.
        [sprite.update_nested_sprites() for sprite in self.all_sprites]
        [sprite.update() for sprite in self.all_sprites if sprite.dirty]

    def render(self, screen):  # noqa: W0613
        self.rects = self.all_sprites.draw(self.screen)

    def sprites_at_position(self, pos):
        mouse = MousePointer(x=pos[0], y=pos[1])

        return pygame.sprite.spritecollide(mouse, self.all_sprites, False)

    # def on_mouse_drag_event(self, event, trigger):
    #     self.log.debug(f'{type(self)}: Mouse Drag Event: {event} {trigger}')
    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     for sprite in collided_sprites:
    #         sprite.on_mouse_drag_event(event, trigger)

    # def on_mouse_drop_event(self, event, trigger):
    #     self.log.debug(f'{type(self)}: Mouse Drop Event: {event} {trigger}')
    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     for sprite in collided_sprites:
    #         sprite.on_mouse_drop_event(event, trigger)

    # def on_left_mouse_drag_event(self, event, trigger):
    #     self.log.debug(f'{type(self)}: Left Mouse Drag Event: {event} {trigger}')
    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     if collided_sprites:
    #         collided_sprites[-1].on_left_mouse_drag_event(event, trigger)

    #     # for sprite in collided_sprites:
    #     #     sprite.on_left_mouse_drag_event(event, trigger)

    # def on_left_mouse_drop_event(self, event, trigger):
    #     self.log.debug(f'{type(self)}: Left Mouse Drop Event: {event} {trigger}')
    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     for sprite in collided_sprites:
    #         sprite.on_left_mouse_drop_event(event, trigger)

    # def on_middle_mouse_drag_event(self, event, trigger):
    #     self.log.info(f'{type(self)}: Middle Mouse Drag Event: {event} {trigger}')
    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     for sprite in collided_sprites:
    #         sprite.on_middle_mouse_drag_event(event, trigger)

    # def on_middle_mouse_drop_event(self, event, trigger):
    #     self.log.info(f'{type(self)}: Middle Mouse Drop Event: {event} {trigger}')
    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     for sprite in collided_sprites:
    #         sprite.on_middle_mouse_drop_event(event, trigger)

    # def on_right_mouse_drag_event(self, event, trigger):
    #     self.log.info(f'{type(self)}: Right Mouse Drag Event: {event} {trigger}')
    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     for sprite in collided_sprites:
    #         sprite.on_right_mouse_drag_event(event, trigger)

    # def on_right_mouse_drop_event(self, event, trigger):
    #     self.log.info(f'{type(self)}: Right Mouse Drop Event: {event} {trigger}')
    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     for sprite in collided_sprites:
    #         sprite.on_right_mouse_drop_event(event, trigger)

    # def on_left_mouse_button_up_event(self, event):
    #     # MOUSEBUTTONUP    pos, button
    #     self.log.debug(f'{type(self)}: Left Mouse Button Up Event: {event}')

    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     for sprite in collided_sprites:
    #         sprite.on_left_mouse_button_up_event(event)

    # def on_middle_mouse_button_up_event(self, event):
    #     # MOUSEBUTTONUP    pos, button
    #     self.log.debug(f'{type(self)}: Middle Mouse Button Up Event: {event}')

    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     for sprite in collided_sprites:
    #         sprite.on_middle_mouse_button_up_event(event)

    # def on_right_mouse_button_up_event(self, event):
    #     # MOUSEBUTTONUP    pos, button
    #     self.log.info(f'{type(self)}: Right Mouse Button Up Event: {event}')

    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     for sprite in collided_sprites:
    #         sprite.on_right_mouse_button_up_event(event)

    # def on_left_mouse_button_down_event(self, event):
    #     # MOUSEBUTTONDOWN  pos, button
    #     self.log.debug(f'{type(self)}: Left Mouse Button Down Event: {event}')

    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     self.log.info(f'ENGINE SPRITES: {collided_sprites}')

    #     # if collided_sprites:
    #     #     collided_sprites[0].on_left_mouse_button_down_event(event)
    #     for sprite in collided_sprites:
    #         sprite.on_left_mouse_button_down_event(event)

    # def on_middle_mouse_button_down_event(self, event):
    #     # MOUSEBUTTONDOWN    pos, button
    #     self.log.debug(f'{type(self)}: Middle Mouse Button Down Event: {event}')

    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     for sprite in collided_sprites:
    #         sprite.on_middle_mouse_button_down_event(event)

    # def on_right_mouse_button_down_event(self, event):
    #     # MOUSEBUTTONDOWN  pos, button
    #     self.log.info(f'{type(self)}: Right Mouse Button Down Event: {event}')

    #     collided_sprites = self.sprites_at_position(pos=event.pos)

    #     for sprite in collided_sprites:
    #         sprite.on_right_mouse_button_down_event(event)

    def on_key_up_event(self, event):
        # Wire up quit by default for escape and q.
        #
        # If a game implements on_key_up_event themselves
        # they'll have to map their quit keys or call super().on_key_up_event()
        if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
            self.scene_manager.quit()

    def on_quit_event(self, event):
        # QUIT             none
        self.log.debug(f'{type(self)}: {event}')

    def on_fps_event(self, event):  # noqa: W0613
        # FPSEVENT is pygame.USEREVENT + 1
        self.log.info(f'Scene "{self.NAME}" ({type(self)}) FPS: {event.fps}')

    def load_resources(self):  # noqa: R0201
        self.log.debug(f'Implement load_resource() in {type(self)}.')
