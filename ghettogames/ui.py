import logging

from pygame import Rect
import pygame

from ghettogames.color import WHITE, BLACKLUCENT
from ghettogames.engine import FontManager
from ghettogames.engine import GameEngine
from ghettogames.sprites import FocusableSingletonBitmappySprite
from ghettogames.sprites import BitmappySprite, RootRootSprite
from ghettogames.sprites import MousePointer

LOG = logging.getLogger('game.ui')
LOG.addHandler(logging.NullHandler())


class MenuBar(FocusableSingletonBitmappySprite):
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
        self.dirty = 1
        self.log.info(f'MENUBAR GROUPS: {groups}')

        pygame.draw.rect(self.image, (255, 255, 255), self.rect)
        pygame.draw.rect(self.image, (255, 255, 255), self.rect, self.border_width)

    def add_menu(self, menu):
        # This makes sure that the menu items get drawn when the menu bar gets drawn.
        self.menu_items[menu.name] = menu
        self.log.info(f'add_menu({menu})')
        menu.image.set_colorkey((255, 255, 255))
        menu.add(self.groups())
        menu.rect.x += self.menu_offset_x
        menu.rect.y += self.menu_offset_y
        self.menu_offset_x += menu.rect.width
        self.log.info(f'Menu Items: {self.menu_items}')

    def add_menu_item(self, menu_item, menu):
        if menu is None:
            self.add_menu(menu=menu_item)
            self.log.info(f'{type(self)} Adding new menu {menu_item}.')
        else:
            self.log.info(f'{type(self)} Adding menu item {menu_item} to menu {menu}.')

        self.dirty = 1

    def update(self):
        for menu_item_name, menu_item in self.menu_items.items():
            menu_item = self.menu_items[menu_item_name]
            self.image.blit(menu_item.image, (menu_item.rect.x, menu_item.rect.y))

        if self.has_focus:
            pygame.draw.rect(self.image, (255, 255, 0), self.rect, 1)

    def on_mouse_motion_event(self, event):
        self.log.info(f'{type(self)} MOUSE MOVE {self.name}')

    def on_mouse_enter_event(self, event):
        self.log.info(f'{type(self)} ENTER MENU {self.name}')
        # Figure out which item was entered.
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.info(f'{type(self)} {self.name} Mouse enter on {self.name} at {mouse}')
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
                self.log.info(f'{type(self)} {self.name} Mouse exit on {self.name} at {mouse}')
                collided_sprite.on_mouse_exit_event(event)

                for menu_item in collided_sprite.menu_items:
                    collided_sprite.menu_items[menu_item].on_mouse_exit_event(event)

        self.has_focus = False
        self.dirty = 1

    def on_left_mouse_button_down_event(self, event):
        # Figure out which item was clicked.
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.info(f'{type(self)} Mouse button down on {self.name} at {mouse}')
                collided_sprite.on_left_mouse_button_down_event(event)

                for menu_item in collided_sprite.menu_items:
                    collided_sprite.menu_items[menu_item].on_left_mouse_button_down_event(event)

        self.dirty = 1

    def on_left_mouse_button_up_event(self, event):
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.info(f'{type(self)} {self.name} Mouse button down on {self.name} at {mouse}')
                collided_sprite.on_left_mouse_button_down_event(event)

                for menu_item in collided_sprite.menu_items:
                   collided_sprite.menu_items[menu_item].on_left_mouse_button_up_event(event)

        self.dirty = 1


class MenuItem(BitmappySprite):
    def __init__(self, x=0, y=0, width=1, height=1, name=None, filename=None,
                 groups=pygame.sprite.LayeredDirty()):
        super().__init__(x=x, y=y, width=width, height=height, name=name, focusable=True,
                         filename=filename, groups=groups)
        self.all_sprites = groups

        self.log.info(f'MENUITEM GROUPS: {groups}')

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

        # Don't set a name for the icon.
        if self.name:
            self.image.fill((255, 255, 255))
            self.image.set_colorkey((255, 255, 255))
            self.text = TextSprite(background_color=self.background_color,
                                   text_color=(0, 0, 0),
                                   x=self.rect.x,
                                   y=self.rect.y,
                                   width=self.width,
                                   height=self.height,
                                   text=self.name,
                                   groups=groups)
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
        self.dirty = 1

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
        self.menu_rect.x = self.rect.x
        self.menu_rect.y = 21

        width = max([self.menu_items[menu_item].rect.width + 20
                     for menu_item
                     in self.menu_items]) * 2.5
        heights = [self.menu_items[menu_item].rect.height for menu_item in self.menu_items]
        height = self.rect.height

        if heights:
            self.log.info(f'{[self.menu_items[menu_item].rect.height for menu_item in self.menu_items]}')
            self.log.info(f'Heights: {heights}')
            heights.append(self.rect.height)
            self.log.info(f'New Heights: {heights}')
            height = sum(heights)

        # Create a new image that is self.height + [menu.height for menu in self.menu_items]
        # Create a new image that is self.width + [menu.width for menu in self.menu_items]
        self.menu_down_image = pygame.Surface((width, height))
        self.menu_down_image.set_colorkey((255, 0, 255))
        self.menu_down_rect = self.menu_down_image.get_rect()
        self.menu_down_rect.x = self.rect.x
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
            self.log.info(f'{type(self)} Adding new menu {menu_item}.')
        else:
            self.log.info(f'{type(self)} Adding menu item {menu_item} to menu {menu}.')

    def update(self):
        # self.log.info(f'Menu Items: {self.menu_items.items()}')
        self.screen.blit(self.image, (self.rect.x, self.rect.y))

        if self.active:
           if self.menu_image and self.menu_rect:
               self.log.info('Trying to draw the menu')
               pygame.display.get_surface().blit(self.menu_image, \
                                                 (self.menu_rect.x, self.menu_rect.y))
        pass

    def on_mouse_motion_event(self, event):
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        # self.log.info(f'{type(self)} MOUSE ITEM MOVE {self.name} at {mouse.rect}')

        # for menu_name in self.menu_items:
        #    menu_item = self.menu_items[menu_name]
        #    self.log.info(f'{menu_item.name} @ {menu_item.rect} mouse @ {mouse.rect}')

        for collided_sprite in collided_sprites:
            if collided_sprite.name in self.menu_items:
                self.log.info(f'Mouse enter on {collided_sprite.name} '
                         f'{collided_sprite.rect} at {mouse.rect}')
                collided_sprite.on_mouse_motion_event(event)

                for submenu in collided_sprite.menu_items:
                   submenu.on_mouse_motion_event(event)

        self.has_focus = False
        self.dirty = 1

    def on_mouse_enter_event(self, event):
        self.log.info(f'{type(self)} ENTER MENU {self.name}')
        # Figure out which item was entered.
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.info(f'Mouse enter on {collided_sprite.name} '
                         f'{collided_sprite.rect} at {mouse.rect}')
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
                log.info(f'Mouse exit on {collided_sprite.name} {collided_sprite.rect} at {mouse}')
                collided_sprite.on_mouse_exit_event(event)

                for submenu in collided_sprite.menu_items:
                    submenu.on_mouse_enter_event(event)

        self.has_focus = False
        self.dirty = 1

    def on_left_mouse_button_up_event(self, event):
        self.log.info(f'{type(self)} Mouse Up {self.name}')
        self.image = self.menu_up_image
        self.rect = self.menu_up_rect
        self.active = 0
        self.dirty = 2
        self.update()

        # Figure out which item was clicked.
        mouse = MousePointer(x=event.pos[0], y=event.pos[1])

        self.log.info(f'Process MOUSE UP {event} at {mouse}')

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                # self.log.info(f'Mouse button up on {collided_sprite.name} at {mouse.rect}')

                self.log.info(f'{type(self)} Clicked Menu Item: Name: {collided_sprite.name}, '
                         f'Width: {collided_sprite.rect.width},'
                         f'Height: {collided_sprite.rect.height}, '
                         f'Clicked X: {mouse.x}, Clicked Y: {mouse.y},'
                         f'my X: {collided_sprite.rect.x}, '
                         f'my Y: {collided_sprite.rect.y}')
                menu_item_callback = collided_sprite.callbacks.get('on_menu_item_event', None)

                if menu_item_callback:
                    menu_item_callback(self, event)
                # Create a menu item clicked event.
                # Emit it to the pygame event subsystem.
                pygame.event.post(
                    pygame.event.Event(GameEngine.MENUEVENT,
                                       {'menu': self,
                                        'menu_item': collided_sprite})
                )
                self.game.on_menu_item_clicked_event()

        self.dirty = 1

    def on_left_mouse_button_down_event(self, event):
        self.log.info(f'{type(self)} Mouse Down {self.name}')
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
                self.log.info(f'{type(collided_sprite)} Mouse button down on '
                         f'{collided_sprite.name} at {mouse.rect}')
                collided_sprite.on_left_mouse_button_down_event(event)

        self.dirty = 1


class Bar(BitmappySprite):
    class BarBar(RootRootSprite):
        def __init__(self, groups):
            super().__init__(groups=groups)
            self.font = FontManager(GameEngine).font()
            (self.image, self.rect) = self.font.render("Success!", (255, 255, 0))

    def __init__(self, y=0, width=32, height=32, groups=None):

        super().__init__(x=0, y=y, width=width, height=height, groups=groups)

        self.bar_bar = Bar.BarBar(groups=groups)


class TextSprite(BitmappySprite):
    class TextBox(RootRootSprite):
        def __init__(self, parent, font, x, y, line_height=15, text='Text', text_color=WHITE,
                     groups=pygame.sprite.LayeredDirty()):
            super().__init__(groups=groups)
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

        def __getattr__(self, attr):
            # Try each proxy in turn
            # Hackery for pygame weirdness.
            # Unfortunately, Pygame does this:
            # self._layer = getattr(self, '_layer', 0)    # Default 0 unless
            # Which causes an attribute lookup error for us on first lookup,
            # since _layer doesn't exist yet.  This is why this method gets called.
            if attr == '_layer':
                return 0

            # This will essentially pass any unhandled events back to the parent.
            for proxy in self.proxies:
                self.log.info(f'Proxy: {proxy}')
                try:
                    return getattr(proxy, attr)
                except AttributeError:
                    self.log.error(f'No proxies for {type(self)}.{attr}')

        #def on_mouse_focus_event(self, event, focus):
        #    self.active_text_color = self.text_hover_color
        #    self.active_background_color = self.background_hover_color

        #def on_mouse_unfocus_event(self, event):
        #    self.active_text_color = self.text_color
        #    self.active_background_color = self.background_color

        #def on_left_mouse_button_down_event(self, event):
        #    self.active_text_color = self.text_click_color
        #    self.active_background_color = self.background_click_color

        #def on_left_mouse_button_up_event(self, event):
        #    self.active_text_color = self.text_hover_color
        #    self.active_background_color = self.background_hover_color

    def __init__(self, x, y, width, height, name=None, background_color=BLACKLUCENT,
                 text_color=WHITE, alpha=0, text='Text', groups=pygame.sprite.LayeredDirty()):
        super().__init__(x=x, y=y, width=width, height=height, name=name, focusable=True,
                         groups=groups)
        self.background_color = (255, 0, 255)
        self.active_color = self.background_color
        self.click_color = (0, 255, 128)
        self.text = text
        self.font_manager = FontManager(GameEngine)
        self.alpha = 0

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

        self.rect = self.image.get_rect()
        self.rect.x += self.x
        self.rect.y += self.y

        self.text_box = TextSprite.TextBox(parent=self,
                                           font=self.font_manager.font(),
                                           x=self.rect.centerx,
                                           y=self.rect.centery,
                                           text=self.text,
                                           text_color=text_color,
                                           groups=groups)

        self.text_box.start_x = self.rect.centerx
        self.text_box.start_y = self.rect.centery

        self.dirty = 1

    def update(self):
        self.dirty = 1
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
        self.active_color = (255, 0, 0)

    def on_mouse_unfocus_event(self, event):
        self.active_color = self.background_color

    def on_left_mouse_button_down_event(self, event):
        self.active_color = self.click_color

    def on_left_mouse_button_up_event(self, event):
        self.active_color = (255, 0, 0)


class ButtonSprite(BitmappySprite):
    """
    """

    def __init__(self, x, y, width, height, name=None,
                 groups=pygame.sprite.LayeredDirty()):
        super().__init__(x=x, y=y, width=width, height=height, name=name,
                         focusable=True, groups=groups)
        self.border_color = (255, 255, 255)
        self.active_color = (128, 128, 128)
        self.inactive_color = (0, 0, 0)
        self.background_color = self.inactive_color

        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y

        self.text = TextSprite(background_color=self.background_color,
                               x=self.rect.x,
                               y=self.rect.y,
                               width=self.width,
                               height=self.height,
                               text=self.name,
                               groups=groups)
        # self.text.rect.center = self.rect.center

        pygame.draw.rect(self.image, self.border_color, Rect(0, 0, self.width, self.height), 1)
        self.dirty = 1

    # def update(self):
    #    pass
        # if self.text:
        #    self.text.background_color = self.background_color
            # self.text.dirty = 1
            # self.text.update()

            # self.log.info(f'Box Width = {self.text.rect.width}')
            # self.log.info(f'Box Height = {self.text.rect.height}')
            # self.log.info(f'Text Box width = {self.text.text_box.rect.width}')
            # self.log.info(f'Text Box height = {self.text.text_box.rect.height}')
            # self.log.info(f'Text Box X: {self.text.x}, {self.text.rect.x}')
            # self.log.info(f'Text Box Y: {self.text.y}, {self.text.rect.y}')

            # self.image.blit(self.text.image, (self.rect.centerx,
            #                                  self.rect.centery,
            #                                  self.text.text_box.rect.width,
            #                                  self.text.text_box.rect.height))

    def on_left_mouse_button_down_event(self, event):
        self.dirty = 1
        self.background_color = self.active_color
        self.update()
        super().on_left_mouse_button_down_event(event)

    def on_left_mouse_button_up_event(self, event):
        self.dirty = 1
        self.background_color = self.inactive_color
        self.update()
        super().on_left_mouse_button_up_event(event)


class CheckboxSprite(ButtonSprite):
    """
    """

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

        self.rect.x = self.x
        self.rect.y = self.y

    def on_left_mouse_button_down_event(self, event):
        pass

    def on_left_mouse_button_up_event(self, event):
        self.dirty = 1
        self.checked = not self.checked
        self.update()
