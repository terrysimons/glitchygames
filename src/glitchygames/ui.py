import logging

from pygame import Rect
import pygame

from glitchygames.color import WHITE, BLACKLUCENT
from glitchygames.engine import FontManager
from glitchygames.engine import GameEngine
from glitchygames import events
from glitchygames.sprites import FocusableSingletonBitmappySprite
from glitchygames.sprites import BitmappySprite, Sprite
from glitchygames.sprites import MousePointer

LOG = logging.getLogger('game.ui')
LOG.addHandler(logging.NullHandler())


class MenuBar(FocusableSingletonBitmappySprite):
    log = LOG

    def __init__(self, x, y, width, height, name=None, groups=pygame.sprite.LayeredDirty()):
        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)
        self.all_sprites = groups
        self.background_color = (0, 255, 0)
        self.border_width = 2
        self.menu_items = {}
        self.menu_offset_x = self.border_width
        self.menu_offset_y = self.border_width
        self.width = width
        self.height = height
        self.has_focus = False
        self.log.debug(f'MENUBAR GROUPS: {groups}')

        pygame.draw.rect(self.image, (255, 255, 255), self.rect)
        pygame.draw.rect(self.image, (255, 255, 255), self.rect, self.border_width)

    def add_menu(self, menu):
        # This makes sure that the menu items get drawn when the menu bar gets drawn.
        self.menu_items[menu.name] = menu
        self.log.debug(f'add_menu({menu})')
        menu.image.set_colorkey((255, 255, 255))
        menu.add(self.groups())
        menu.rect.x += self.menu_offset_x
        menu.rect.y += self.menu_offset_y
        self.menu_offset_x += menu.rect.width
        self.log.debug(f'Menu Items: {self.menu_items}')

    def add_menu_item(self, menu_item, menu):
        if menu is None:
            self.add_menu(menu=menu_item)
            self.log.debug(f'{type(self)} Adding new menu {menu_item}.')
        else:
            self.log.debug(f'{type(self)} Adding menu item {menu_item} to menu {menu}.')

        self.dirty = 1

    def update(self):
        for menu_item_name, menu_item in self.menu_items.items():
            menu_item = self.menu_items[menu_item_name]
            self.image.blit(menu_item.image, (menu_item.rect.x, menu_item.rect.y))

        if self.has_focus:
            pygame.draw.rect(self.image, (255, 255, 0), self.rect, 1)

    def on_mouse_motion_event(self, event):
        self.log.debug(f'{type(self)} MOUSE MOVE {self.name}')

    def on_mouse_enter_event(self, event):
        self.log.debug(f'{type(self)} ENTER MENU {self.name}')
        # Figure out which item was entered.
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.debug(f'{type(self)} {self.name} Mouse enter on {self.name} at {mouse}')
                collided_sprite.on_mouse_enter_event(event)

                for menu_item in collided_sprite.menu_items:
                    collided_sprite.menu_items[menu_item].on_mouse_enter_event(event)

        self.has_focus = True
        self.dirty = 1

    def on_mouse_exit_event(self, event):
        # Figure out which item was entered.
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.debug(f'{type(self)} {self.name} Mouse exit on {self.name} at {mouse}')
                collided_sprite.on_mouse_exit_event(event)

                for menu_item in collided_sprite.menu_items:
                    collided_sprite.menu_items[menu_item].on_mouse_exit_event(event)

        self.has_focus = False
        self.dirty = 1

    def on_left_mouse_button_down_event(self, event):
        # Figure out which item was clicked.
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            # if sprite.name in self.menu_items:
            if type(sprite) == MenuItem:
                self.log.debug(f'{type(self)} Mouse button down on {self.name} at {mouse}')
                sprite.on_left_mouse_button_down_event(event)

                for menu_item in sprite.menu_items:
                    sprite.menu_items[menu_item].on_left_mouse_button_down_event(event)

        self.dirty = 1

    def on_left_mouse_button_up_event(self, event):
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            # if sprite.name in self.menu_items:
            if type(sprite) == MenuItem:
                self.log.debug(f'{type(self)} {self.name} '
                               f'Mouse button up on {self.name} at {mouse}')
                sprite.on_left_mouse_button_down_event(event)

                for menu_item in sprite.menu_items:
                    sprite.menu_items[menu_item].on_left_mouse_button_up_event(event)

        self.dirty = 1


class MenuItem(BitmappySprite):
    log = LOG

    def __init__(self, x=0, y=0, width=1, height=1, name=None, filename=None, parent=None,
                 groups=pygame.sprite.LayeredDirty()):
        super().__init__(x=x, y=y, width=width, height=height, name=name, focusable=True,
                         filename=filename, groups=groups)
        self.all_sprites = groups

        self.log.debug(f'MENUITEM GROUPS: {groups}')

        self.background_color = (255, 0, 255)
        self.border_width = 2
        self.menu_items = {}
        self.menu_offset_x = self.border_width
        self.menu_offset_y = self.border_width
        self.menu_image = None
        self.menu_rect = None
        self.menu_down_image = None
        self.menu_down_rect = None
        self.menu_up_image = None
        self.menu_up_rect = None
        self.active = False
        self.name = name
        self.parent = parent

        # Don't set a name for the icon.
        if self.name:
            self.image.fill((255, 255, 255))
            self.image.set_colorkey((255, 255, 255))
            self.text = TextSprite(
                background_color=self.background_color,
                text_color=(0, 0, 0),
                x=self.rect.x,
                y=self.rect.y,
                width=self.width,
                height=self.height,
                text=self.name,
                parent=parent,
                groups=groups
            )
            self.text.image.set_colorkey((255, 0, 255))
            self.text.add(groups)
            # self.image.blit(self.text.text_box.image, (0, 0))
            # self.image = self.text.text_box.image
            # self.rect.x = self.text.rect.x
            # self.rect.y = self.text.rect.y

        self.menu_up_image = self.image
        self.menu_up_rect = self.rect
        self.menu_down_image = self.menu_up_image
        self.menu_down_rect = self.menu_up_rect

    def add(self, *groups):
        # super().add(*groups)

        # There's something funky with MRO and pygame
        # doing things this way avoids dirtier tricks.
        try:
            text = getattr(self, 'text')
            text.add(*groups)
        except AttributeError:
            pass

    def add_menu(self, menu):
        menu.image.set_colorkey((255, 0, 255))
        menu.add(self.groups())
        menu.add(self.all_sprites)
        if not len(self.menu_items.keys()):
            self.menu_offset_y += self.rect.height
        else:
            menu.rect.x += self.menu_offset_x
            menu.rect.y += self.menu_offset_y
            self.menu_offset_y += menu.rect.height

        self.menu_items[menu.name] = menu

        # Now recreate the menu image for later use.
        self.menu_image = pygame.Surface((400, 300))
        self.menu_image.convert()
        self.menu_image.set_colorkey((255, 0, 255))
        self.menu_image.fill((255, 255, 255))
        self.menu_rect = self.menu_image.get_rect()
        self.menu_rect.x = self.x
        self.menu_rect.y = 21

        width = max([self.menu_items[menu_item].rect.width + 20
                     for menu_item
                     in self.menu_items]) * 2.5
        heights = [self.menu_items[menu_item].rect.height for menu_item in self.menu_items]
        height = self.rect.height

        if heights:
            self.log.debug(f'Heights: {heights}')
            heights.append(self.rect.height)
            self.log.debug(f'New Heights: {heights}')
            height = sum(heights)

        # Create a new image that is self.height + [menu.height for menu in self.menu_items]
        # Create a new image that is self.width + [menu.width for menu in self.menu_items]
        self.menu_down_image = pygame.Surface((width, height))
        self.menu_down_image.set_colorkey((255, 0, 255))
        self.menu_down_rect = self.menu_down_image.get_rect()
        self.menu_down_rect.x = self.x
        self.menu_down_rect.y = self.rect.y
        self.menu_down_image.fill((255, 255, 255))
        self.rect.width = self.menu_down_rect.width
        self.rect.height = self.menu_down_rect.height

        # Put ourselves at the top of the list.
        self.menu_down_image.blit(self.image, (0, self.rect.y))

        y_offset = self.rect.height
        for menu_name in self.menu_items:
            menu_item = self.menu_items[menu_name]
            menu_item.rect.y = y_offset
            menu_item.rect.width = menu_item.text.width
            menu_item.rect.height = menu_item.text.height
            self.menu_down_image.blit(menu_item.image, (menu_item.rect.x, menu_item.rect.y))
            y_offset += menu_item.rect.height

    def add_menu_item(self, menu_item, menu):
        if menu is None:
            self.add_menu(menu=menu_item)
            self.log.debug(f'{type(self)} Adding new menu {menu_item}.')
        else:
            self.log.debug(f'{type(self)} Adding menu item {menu_item} to menu {menu}.')

    def update(self):
        # self.log.debug(f'Menu Items: {self.menu_items.items()}')
        self.screen.blit(self.image, (self.rect.x, self.rect.y))

        if self.active:
            if self.menu_image and self.menu_rect:
                self.log.debug('Trying to draw the menu')
                pygame.display.get_surface().blit(self.menu_image,
                                                  (self.menu_rect.x, self.menu_rect.y))

    def on_mouse_motion_event(self, event):
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        # self.log.debug(f'{type(self)} MOUSE ITEM MOVE {self.name} at {mouse.rect}')

        # for menu_name in self.menu_items:
        #    menu_item = self.menu_items[menu_name]
        #    self.log.debug(f'{menu_item.name} @ {menu_item.rect} mouse @ {mouse.rect}')

        for collided_sprite in collided_sprites:
            if collided_sprite.name in self.menu_items:
                self.log.debug(
                    f'Mouse enter on {collided_sprite.name} '
                    f'{collided_sprite.rect} at {mouse.rect}'
                )
                collided_sprite.on_mouse_motion_event(event)

                for submenu in collided_sprite.menu_items:
                    submenu.on_mouse_motion_event(event)

        self.has_focus = False
        self.dirty = 1

    def on_mouse_enter_event(self, event):
        self.log.debug(f'{type(self)} ENTER MENU {self.name}')
        # Figure out which item was entered.
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.debug(
                    f'Mouse enter on {collided_sprite.name} '
                    f'{collided_sprite.rect} at {mouse.rect}'
                )
                collided_sprite.on_mouse_enter_event(event)

                for submenu in collided_sprite.menu_items:
                    submenu.on_mouse_enter_event(event)

        self.has_focus = True
        self.dirty = 1

    def on_mouse_exit_event(self, event):
        # Figure out which item was entered.
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.debug(
                    f'Mouse exit on {collided_sprite.name} '
                    f'{collided_sprite.rect} at {mouse}'
                )
                collided_sprite.on_mouse_exit_event(event)

                for submenu in collided_sprite.menu_items:
                    submenu.on_mouse_enter_event(event)

        self.has_focus = False
        self.dirty = 1

    def on_left_mouse_button_up_event(self, event):
        self.log.debug(f'{type(self)} Mouse Up {self.name}')
        self.image = self.menu_up_image
        self.rect = self.menu_up_rect
        self.active = 0
        self.dirty = 2
        self.update()

        # Figure out which item was clicked.
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        self.log.debug(f'Process MOUSE UP {event} at {mouse}')

        sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            # if collided_sprite.name in self.menu_items:
            if type(sprite) == MenuItem:
                self.log.debug(f'Mouse button up on {sprite.name} at {mouse.rect}')

                self.log.debug(
                    f'{type(self)} Clicked Menu Item: Name: {sprite.name}, '
                    f'Width: {sprite.rect.width},'
                    f'Height: {sprite.rect.height}, '
                    f'Clicked X: {mouse.rect.x}, Clicked Y: {mouse.rect.y},'
                    f'my X: {sprite.rect.x}, '
                    f'my Y: {sprite.rect.y}'
                )
                menu_item_callback = sprite.callbacks.get('on_menu_item_event', None)

                if menu_item_callback:
                    menu_item_callback(self, event)
                # Create a menu item clicked event.
                # Emit it to the pygame event subsystem.
                pygame.event.post(
                    pygame.event.Event(events.MENUEVENT,
                                       {'menu': self,
                                        'menu_item': sprite})
                )
                # self.game.on_menu_item_clicked_event()

        self.dirty = 1

    def on_left_mouse_button_down_event(self, event):
        self.log.debug(f'{type(self)} Mouse Down {self.name}')
        self.image = self.menu_down_image
        self.rect = self.menu_down_rect
        self.active = 1
        self.dirty = 2

        self.update()

        # Figure out which item was clicked.
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.debug(
                    f'{type(collided_sprite)} Mouse button down on '
                    f'{collided_sprite.name} at {mouse.rect}'
                )
                collided_sprite.on_left_mouse_button_down_event(event)

        self.dirty = 1


class TextSprite(BitmappySprite):
    log = LOG

    class TextBox(Sprite):
        log = LOG

        def __init__(self, font, x, y, line_height=15, text='Text', text_color=WHITE, parent=None,
                     groups=pygame.sprite.LayeredDirty()):
            super().__init__(x=x, y=y, width=0, height=0, parent=parent, groups=groups)
            self.start_x = x
            self.start_y = y
            self.line_height = line_height
            self.text_color = text_color
            self.text_hover_color = (255, 255, 255)
            self.text_click_color = (63, 127, 255)
            self.background_color = (255, 0, 255)
            self.background_hover_color = (0, 255, 128)
            self.background_click_color = (255, 127, 63)
            self.active_text_color = self.text_color
            self.active_background_color = self.background_color
            self.font = font
            self.name = text
            self.parent = parent
            self.proxies = [parent]
            (self.image, self.rect) = self.font.render(text, fgcolor=self.active_text_color)
            # , bgcolor=self.active_background_color)

        def print(self, surface, string):
            (self.image, self.rect) = self.font.render(string, fgcolor=self.active_text_color)
            # , bgcolor=self.active_background_color)
            self.image.set_colorkey((255, 0, 255))
            self.image.convert()

            self.rect.centerx = self.x
            self.rect.centery = self.y
            self.y += self.line_height
            self.dirty = 1

        def reset(self):
            self.x = self.start_x
            self.y = self.start_y
            self.dirty = 1

        def indent(self):
            self.x += 10
            self.dirty = 1

        def unindent(self):
            self.x -= 10
            self.dirty = 1

        @property
        def x(self):
            return self.start_x

        @x.setter
        def x(self, new_x):
            self.rect.x = self.parent.rect.centerx if self.parent else new_x
            self.start_x = self.rect.x
            # self.slider_knob.rect.centerx = self.rect.x + self.slider_knob.value
            # self.text_sprite.x = 240
            # self.text_sprite.text_box.x = self.parent.rect.centerx \
            #     if self.parent else self.rect.centerx
            self.dirty = 1

        @property
        def y(self):
            return self.start_y

        @y.setter
        def y(self, new_y):
            self.rect.centery = self.parent.rect.centery if self.parent else new_y
            self.start_y = self.rect.y
            # self.text_sprite.y = self.parent.rect.y if self.parent else self.rect.y
            # self.text_sprite.text_box.y = self.parent.rect.centery \
            #     if self.parent else self.rect.centery

            self.dirty = 1

        # def update_nested_sprites(self):
        #     self.slider_knob.dirty = self.dirty
        #     self.text.dirty = self.dirty
        #     # self.text_sprite.text.dirty = self.dirty

        # def on_mouse_focus_event(self, event, focus):
        #     self.active_text_color = self.text_hover_color
        #     self.active_background_color = self.background_hover_color

        # def on_mouse_unfocus_event(self, event):
        #     self.active_text_color = self.text_color
        #     self.active_background_color = self.background_color

        # def on_left_mouse_button_down_event(self, event):
        #     self.active_text_color = self.text_click_color
        #     self.active_background_color = self.background_click_color

        # def on_left_mouse_button_up_event(self, event):
        #     self.active_text_color = self.text_hover_color
        #     self.active_background_color = self.background_hover_color

    def __init__(self, x, y, width, height, name=None, background_color=BLACKLUCENT,
                 text_color=WHITE, alpha=0, text='Text', parent=None,
                 groups=pygame.sprite.LayeredDirty()):
        super().__init__(x=x, y=y, width=width, height=height, name=name, focusable=True,
                         parent=parent, groups=groups)
        self.background_color = (255, 0, 255)
        self.active_color = self.background_color
        self.click_color = (0, 255, 128)
        self.hover_color = (255, 255, 0)
        self.text = text
        self.font_manager = FontManager(GameEngine)
        self.alpha = 0
        self.parent = parent

        if not self.alpha:
            self.image.set_colorkey(self.background_color)
            self.image.convert()
        else:
            # Enabling set_alpha() and also setting a color
            # key will let you hide the background
            # but things that are blited otherwise will
            # be translucent.  This can be an easy
            # hack to get a translucent image which
            # does not have a border, but it causes issues
            # with edge-bleed.
            #
            # What if we blitted the translucent background
            # to the screen, then copied it and used the copy
            # to write the text on top of when translucency
            # is set?  That would allow us to also control
            # whether the text is opaque or translucent, and
            # it would also allow a different translucency level
            # on the text than the window.
            self.image.set_alpha(self.alpha)
            self.image.convert_alpha()

        self.text_box = TextSprite.TextBox(
            font=self.font_manager.font(),
            x=x,
            y=x,
            text=self.text,
            text_color=text_color,
            parent=self,
            groups=groups
        )

        self.text_box.start_x = self.rect.centerx
        self.text_box.start_y = self.rect.centery

        self.proxies = [self.parent]

    @property
    def x(self):
        return self.rect.x

    @x.setter
    def x(self, new_x):
        self.rect.x = new_x
        self.text_box.start_x = self.parent.rect.centerx if self.parent else new_x
        # self.text_box.start_x = self.x
        self.dirty = 1

    @property
    def y(self):
        return self.rect.y

    @y.setter
    def y(self, new_y):
        self.rect.y = new_y
        self.text_box.start_y = self.parent.rect.centery if self.parent else new_y
        # self.text_box.start_y = self.y
        self.dirty = 1

    def update_nested_sprites(self):
        self.text_box.dirty = self.dirty

    def update(self):
        self.image.fill(self.active_color)

        self.text_box.reset()
        self.text_box.print(self.image, f'{self.text}')

    def add(self, *groups):
        super().add(*groups)

        # There's something funky with MRO and pygame
        # doing things this way avoids dirtier tricks.
        try:
            text_box = getattr(self, 'text_box')
            text_box.add(*groups)
        except AttributeError:
            pass

    def on_mouse_focus_event(self, event, focus):
        self.active_color = self.hover_color
        self.dirty = 1

    def on_mouse_unfocus_event(self, event):
        self.active_color = self.background_color
        self.dirty = 1

    def on_left_mouse_button_down_event(self, event):
        self.active_color = self.click_color
        self.dirty = 1

    def on_left_mouse_button_up_event(self, event):
        self.active_color = self.background_color
        self.dirty = 1


class ButtonSprite(BitmappySprite):
    """
    """
    log = LOG

    def __init__(self, x, y, width, height, name=None, parent=None,
                 groups=pygame.sprite.LayeredDirty()):
        super().__init__(x=x, y=y, width=width, height=height, name=name,
                         focusable=True, parent=parent, groups=groups)
        self.border_color = (255, 255, 255)
        self.active_color = (128, 128, 128)
        self.inactive_color = (0, 0, 0)
        self.background_color = self.inactive_color

        self.text = TextSprite(
            background_color=self.background_color,
            x=self.parent.rect.centerx if parent else self.x,
            y=self.parent.rect.centery if parent else self.y,
            width=self.width,
            height=self.height,
            text=self.name,
            parent=self,
            groups=groups
        )
        self.text.rect.center = self.rect.center

        pygame.draw.rect(self.image, self.border_color, Rect(0, 0, self.width, self.height), 1)

    # def update(self):
    #     if self.text:
    #         self.text.background_color = self.background_color
    #         self.text.dirty = 1
    #         self.text.update()

    #         self.log.debug(f'Box Width = {self.text.rect.width}')
    #         self.log.debug(f'Box Height = {self.text.rect.height}')
    #         self.log.debug(f'Text Box width = {self.text.text_box.rect.width}')
    #         self.log.debug(f'Text Box height = {self.text.text_box.rect.height}')
    #         self.log.debug(f'Text Box X: {self.text.x}, {self.text.rect.x}')
    #         self.log.debug(f'Text Box Y: {self.text.y}, {self.text.rect.y}')

    #         self.image.blit(self.text.image, (self.rect.centerx,
    #                                          self.rect.centery,
    #                                          self.text.text_box.rect.width,
    #                                          self.text.text_box.rect.height))

    @property
    def x(self):
        return self.rect.x

    @x.setter
    def x(self, new_x):
        self.rect.x = new_x
        self.text.x = self.parent.rect.centerx if self.parent else new_x
        self.dirty = 1

    @property
    def y(self):
        return self.rect.y

    @y.setter
    def y(self, new_y):
        self.rect.y = new_y
        self.text.y = self.parent.rect.centery if self.parent else new_y
        self.dirty = 1

    def update_nested_sprites(self):
        self.text.dirty = self.dirty

    def on_left_mouse_button_down_event(self, event):
        self.background_color = self.active_color
        # self.update()
        super().on_left_mouse_button_down_event(event)
        self.dirty = 1

    def on_left_mouse_button_up_event(self, event):
        self.background_color = self.inactive_color
        # self.update()
        super().on_left_mouse_button_up_event(event)
        self.dirty = 1


class CheckboxSprite(ButtonSprite):
    """
    """
    log = LOG

    def __init__(self, x, y, width, height, name=None, callbacks=None,
                 groups=pygame.sprite.LayeredDirty()):
        super().__init__(x=x, y=y, width=width, height=height, name=name,
                         groups=groups)

        self.checked = False
        self.color = (128, 128, 128)

    def update(self):
        if not self.checked:
            self.image.fill((0, 0, 0))

        pygame.draw.rect(self.image, self.color, Rect(0, 0, self.width, self.height), 1)

        if self.checked:
            pygame.draw.line(self.image, self.color, (0, 0), (self.width - 1, self.height - 1), 1)
            pygame.draw.line(self.image, self.color, (0, self.height - 1), (self.width - 1, 0), 1)

    def on_left_mouse_button_down_event(self, event):
        pass

    def on_left_mouse_button_up_event(self, event):
        self.checked = not self.checked
        # self.update()
        self.dirty = 1


class TextBoxSprite(BitmappySprite):
    """
    """
    log = LOG

    def __init__(self, x, y, width, height, name=None, callbacks=None, parent=None,
                 groups=pygame.sprite.LayeredDirty()):
        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            parent=parent,
            groups=groups
        )
        self.value = None
        self.background_color = (0, 0, 0)
        self.border_width = 1

        self.callbacks = callbacks

        self.text_box = TextSprite(
            background_color=self.background_color,
            x=x,
            y=y,
            width=self.width - self.border_width,
            height=self.height - self.border_width,
            text=self.value,
            parent=self,
            groups=groups
        )

        self.x = x
        self.y = y

        self.text_box.x = self.x
        self.text_box.y = self.y

        self.proxies = [self.parent]

    def update_nested_sprites(self):
        self.text_box.dirty = self.dirty

    def update(self):
        if self.text_box:
            self.text_box.background_color = self.background_color

            self.image.blit(self.text_box.image, (self.x, self.y, self.width, self.height))

        # TODO: Update this to support hover/click/etc...
        if self.border_width:
            pygame.draw.rect(
                self.image,
                (128, 128, 128),
                Rect(0, 0, self.width, self.height),
                self.border_width
            )

    def on_left_mouse_button_down_event(self, event):
        self.background_color = (128, 128, 128)
        self.dirty = 1

    def on_left_mouse_button_up_event(self, event):
        self.background_color = (0, 0, 0)
        self.dirty = 1


class SliderSprite(BitmappySprite):
    log = LOG

    class SliderKnobSprite(BitmappySprite):
        log = LOG

        def __init__(self, x, y, width, height, name=None, parent=None,
                     groups=pygame.sprite.LayeredDirty()):
            super().__init__(
                x=x,
                y=y,
                width=width,
                height=height,
                name=name,
                parent=parent,
                groups=groups
            )

            self.value = 0

            self.image.fill((255, 255, 255))
            self.rect = Rect(x, y, self.width, self.height)
            self.x = x
            self.y = y

        def on_left_mouse_button_down_event(self, event):
            self.dirty = 1
            self.value = event.pos[0] - self.parent.x

            # Hack
            if self.value > 255:
                self.value = 255
            elif self.value < 0:
                self.value = 0

            self.rect.centerx = self.parent.x + self.value if self.parent else self.x + self.value
            super().on_left_mouse_button_down_event(event)

        def on_left_mouse_drag_event(self, event, trigger):
            # There's not a good way to pass any useful info, so for now, pass None
            # since we're not using the event for anything in this class.
            self.on_left_mouse_button_down_event(event)
            self.dirty = 1

    def __init__(self, x, y, width, height, name=None, parent=None,
                 groups=pygame.sprite.LayeredDirty()):
        # TODO: If even, make the line 2x thick?
        if height % 2 == 0:
            height -= 1

        super().__init__(
            x=x,
            y=y,
            width=width + 20,
            height=height,
            name=name,
            parent=parent,
            groups=groups
        )

        # self.text_sprite = TextBoxSprite(
        #     x=257,
        #     y=self.rect.y,
        #     width=40,
        #     height=16,
        #     name=str((0, 0, 0)),
        #     parent=self,
        #     groups=groups,
        # )
        self.text_sprite = TextSprite(
            x=257,
            y=self.rect.y,
            width=40,
            height=16,
            name=str((0, 0, 0)),
            parent=self,
            groups=groups,
        )

        self.slider_knob = SliderSprite.SliderKnobSprite(
            x=x,
            y=y - 1,
            width=self.height * 2 - 1,
            height=self.height * 2 - 1,
            name=name,
            parent=self,
            groups=groups
        )

        self.slider_knob.value = 0

        self.text_sprite.text = self.slider_knob.value

        self.slider_knob.rect.centerx = self.rect.x + self.slider_knob.value
        self.slider_knob.rect.y = self.rect.centery - self.rect.height + 1
        self.slider_knob.dirty = 1

        self.text_sprite.border_width = 1
        # self.text_sprite.x = self.rect.right
        # self.text_sprite.y = self.rect.centery

        # This is the stuff pygame really cares about.
        self.image = pygame.Surface((self.width, self.height))
        self.rect = self.image.get_rect()
        self.background = pygame.Surface((self.width, self.height))
        # self.image.fill((255, 255, 255))
        self.x = x
        self.y = y
        self.slider_knob.rect.centerx = self.rect.x + self.slider_knob.value
        self.text_sprite.y = self.parent.rect.y if self.parent else self.rect.y

        # self.image.blit(self.text_sprite.image, (0, 0))

    @property
    def value(self):
        return self.slider_knob.value

    @value.setter
    def value(self, value):
        self.slider_knob.value = value

    @property
    def x(self):
        return self.rect.x

    @x.setter
    def x(self, new_x):
        self.rect.x = new_x
        self.slider_knob.rect.centerx = self.rect.x + self.slider_knob.value
        self.text_sprite.x = 240
        # self.text_sprite.text_box.x = self.parent.rect.centerx \
        #     if self.parent else self.rect.centerx
        self.dirty = 1

    @property
    def y(self):
        return self.rect.y

    @y.setter
    def y(self, new_y):
        self.rect.y = new_y
        self.text_sprite.y = self.parent.rect.y if self.parent else self.rect.y
        # self.text_sprite.text_box.y = self.parent.rect.centery \
        #     if self.parent else self.rect.centery

        self.dirty = 1

    def update_nested_sprites(self):
        self.slider_knob.dirty = self.dirty
        self.text_sprite.dirty = self.dirty
        # self.text_sprite.text.dirty = self.dirty

    def update(self):

        pygame.draw.rect(
            self.image,
            (255, 255, 0),
            Rect(self.x, self.rect.y, self.rect.width, self.rect.height),
            self.width
        )

        pygame.draw.rect(
            self.image,
            (255, 0, 0),
            Rect(self.rect.centerx, self.rect.centery, self.rect.width, self.rect.height),
            1
        )
        self.text_sprite.value = self.slider_knob.value
        self.text_sprite.text_box.text = self.slider_knob.value

        self.image.fill((0, 0, 0))

        color = (255, 255, 255)

        for i in range(256):
            color = (i, i, i)

            if self.name == 'R':
                color = (i, 0, 0)
            elif self.name == 'G':
                color = (0, i, 0)
            elif self.name == 'B':
                color = (0, 0, i)

            pygame.draw.line(
                self.image,
                color,
                (i, self.height // 2 - 1),
                (i, self.height // 2),
                1
            )

            pygame.draw.line(
                self.image,
                color,
                (i, self.height // 2),
                (i, self.height // 2),
                1
            )

            pygame.draw.line(
                self.image,
                color,
                (i, self.height // 2 + 1),
                (i, self.height // 2),
                1
            )

    def on_left_mouse_button_down_event(self, event):
        self.slider_knob.on_left_mouse_button_down_event(event)
        super().on_left_mouse_button_down_event(event)
        self.dirty = 1

    def on_left_mouse_drag_event(self, event, trigger):
        self.on_left_mouse_button_down_event(event)
        # There's not a good way to pass any useful info, so for now, pass None
        # since we're not using the event for anything in this class.
        self.slider_knob.on_left_mouse_drag_event(event, trigger)
        super().on_left_mouse_drag_event(event, trigger)
        self.dirty = 1


class ColorWellSprite(BitmappySprite):
    log = LOG

    def __init__(self, x, y, width, height, name, parent=None, groups=pygame.sprite.LayeredDirty()):
        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            parent=parent,
            groups=groups
        )
        self.red = 0
        self.green = 0
        self.blue = 0

        self.text_sprite = TextBoxSprite(
            x=self.rect.midleft[0] + width,
            y=self.rect.centery - 10,
            width=100,
            height=20,
            name=str(self.active_color),
            parent=self,
            groups=groups
        )

        self.text_sprite.border_width = 1
        # self.text_sprite.rect.midleft = self.rect.midright

    @property
    def active_color(self):
        return (self.red, self.green, self.blue)

    @active_color.setter
    def active_color(self, active_color):
        self.red = active_color[0]
        self.green = active_color[1]
        self.blue = active_color[2]
        self.dirty = 1

    @property
    def hex_color(self):
        hex_str = '{:02X}'
        red, green, blue = self.active_color

        red = hex_str.format(red)
        green = hex_str.format(green)
        blue = hex_str.format(blue)

        return f'#{red}{green}{blue}'

    def update_nested_sprites(self):
        self.text_sprite.dirty = 1

    def update(self):
        pygame.draw.rect(self.image, (128, 128, 255), Rect(0, 0, self.width, self.height), 1)
        pygame.draw.rect(self.image, self.active_color, Rect(1, 1, self.width - 2, self.height - 2))

        self.text_sprite.value = str(self.active_color)
        self.text_sprite.text_box.text = self.hex_color
        self.text_sprite.dirty = 1


class InputDialog(BitmappySprite):
    """
    """
    log = LOG

    def __init__(self, x, y, width, height, name=None, dialog_text='Would you like to do a thing?',
                 confirm_text='Confirm', cancel_text='Cancel', callbacks=None,
                 parent=None, groups=pygame.sprite.LayeredDirty()):
        super().__init__(x=x, y=y, width=width, height=height, name=name, parent=parent,
                         groups=groups)
        self.background_color = (0, 0, 0)
        self.border_width = 1
        self.width = width

        self.dialog_text_sprite = TextBoxSprite(
            name=dialog_text,
            x=self.rect.x,
            y=self.rect.y,
            width=self.width // 2,
            height=20,
            parent=self,
            groups=groups
        )
        self.dialog_text_sprite.rect.x = self.rect.x
        self.dialog_text_sprite.text_box.rect.center = self.dialog_text_sprite.rect.center
        self.dialog_text_sprite.dirty = 1
        self.dialog_text_sprite.text_box.dirty = 1

        self.dialog_text_sprite.text_box.text = dialog_text
        self.confirm_button = ButtonSprite(
            name=confirm_text,
            x=self.rect.x,
            y=self.rect.y,
            width=75,
            height=20,
            groups=groups
        )
        self.cancel_button = ButtonSprite(
            name=cancel_text,
            x=self.rect.x,
            y=self.rect.y,
            width=75,
            height=20,
            groups=groups
        )

        # self.dialog_text_sprite.rect.center = self.rect.center
        # self.confirm_button.rect.bottomright = self.rect.bottomright
        # self.confirm_button.rect.x -= 20
        # self.confirm_button.rect.y -= 20
        # self.cancel_button.rect.bottomright = self.confirm_button.rect.bottomleft
        # self.cancel_button.rect.x -= 20

        # self._dirty = 1

        self.cancel_button.x = self.rect.bottomright[0] - self.cancel_button.width
        self.cancel_button.y = self.rect.bottomright[1] - self.cancel_button.height
        self.confirm_button.x = self.cancel_button.rect.left - self.cancel_button.width
        self.confirm_button.y = self.cancel_button.rect.top
        # self.confirm_button.update_nested_sprites()

    def update_nested_sprites(self):
        self.cancel_button.dirty = self.dirty
        self.confirm_button.dirty = self.dirty

    def update(self):
        # Draw the bounding box.
        pygame.draw.rect(
            self.image,
            (128, 128, 128),
            Rect(0, 0, self.width, self.height),
            self.border_width
        )

        self.dialog_text_sprite.dirty = 1
        self.cancel_button.dirty = 1
        self.confirm_button.dirty = 1

        self.screen.blit(
            self.dialog_text_sprite.image,
            (self.dialog_text_sprite.rect.x, self.dialog_text_sprite.rect.y)
        )
        self.screen.blit(
            self.cancel_button.image,
            (self.cancel_button.rect.x, self.cancel_button.rect.y)
        )
        self.screen.blit(
            self.confirm_button.image,
            (self.confirm_button.rect.x, self.confirm_button.rect.y)
        )

        # Draw the buttons
        # Draw the text input field
