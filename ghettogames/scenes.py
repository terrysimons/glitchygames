import logging

import pygame

from ghettogames.color import BLACK
from ghettogames.events import ResourceManager, EventManager
from ghettogames.mouse import MousePointer

log = logging.getLogger('game.scenes')
log.addHandler(logging.NullHandler())

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

    # TODO: Need to decouple the FPS behavior
    # def on_fps_event(self, event):  # noqa: W0613
    #     # FPSEVENT is pygame.USEREVENT + 1
    #     log.info(f'{type(self)}: {GameEngine.FPS}')
