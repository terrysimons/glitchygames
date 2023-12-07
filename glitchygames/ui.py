#!/usr/bin/env python3
"""GlitchyGames UI classes."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Self

import pygame
from pygame import Rect

from glitchygames import events
from glitchygames.color import BLACKLUCENT, WHITE
from glitchygames.engine import GameEngine
from glitchygames.events.mouse import MousePointer
from glitchygames.fonts import FontManager
from glitchygames.sprites import (
    BitmappySprite,
    FocusableSingletonBitmappySprite,
    Sprite,
)

if TYPE_CHECKING:
    from collections.abc import Callable

LOG = logging.getLogger('game.ui')
LOG.addHandler(logging.NullHandler())


class MenuBar(FocusableSingletonBitmappySprite):
    """A menu bar class."""

    log = LOG

    def __init__(self: Self, x: int, y: int, width: int, height: int, name: str | None = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize a MenuBar.

        Args:
            x (int): The x coordinate of the menu bar.
            y (int): The y coordinate of the menu bar.
            width (int): The width of the menu bar.
            height (int): The height of the menu bar.
            name (str | None): The name of the menu bar.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

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

        # Always refresh the menu bar.
        self.dirty = 2

    def add_menu(self: Self, menu: MenuItem) -> None:
        """Add a menu to the menu bar.

        Args:
            menu (MenuItem): The menu to add.

        Returns:
            None
        """
        # This makes sure that the menu items get drawn when the menu bar gets drawn.
        self.menu_items[menu.name] = menu
        self.log.debug(f'add_menu({menu})')
        menu.image.set_colorkey((255, 255, 255))
        menu.add(self.groups())
        menu.rect.x += self.menu_offset_x
        menu.rect.y += self.menu_offset_y
        self.menu_offset_x += menu.rect.width
        self.log.debug(f'Menu Items: {self.menu_items}')

    def add_menu_item(self: Self, menu_item: MenuItem, menu: MenuBar | None = None) -> None:
        """Add a menu item to the menu bar.

        Args:
            menu_item (MenuItem): The menu item to add.
            menu (MenuBar | None): The menu to add the menu item to.

        Returns:
            None
        """
        if menu is None:
            self.add_menu(menu=menu_item)
            self.log.debug(f'{type(self)} Adding new menu {menu_item}.')
        else:
            self.log.debug(f'{type(self)} Adding menu item {menu_item} to menu {menu}.')

    def update(self: Self) -> None:
        """Update the menu bar.

        Args:
            None

        Returns:
            None
        """
        for menu_item in self.menu_items.values():
            # menu_item = self.menu_items[menu_item_name]
            self.image.blit(menu_item.image, (menu_item.rect.x, menu_item.rect.y))

        if self.has_focus:
            pygame.draw.rect(self.image, (255, 255, 0), self.rect, 1)

    def on_mouse_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} MOUSE MOVE {self.name}')

    def on_mouse_enter_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse enter events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} ENTER MENU {self.name}')
        # Figure out which item was entered.
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse,
            group=self.all_sprites,
            dokill=False
        )

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

    def on_mouse_exit_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse exit events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Figure out which item was entered.
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse,
            group=self.all_sprites,
            dokill=False
        )

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

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Figure out which item was clicked.
        mouse = MousePointer(pos=event.pos)

        sprites = pygame.sprite.spritecollide(sprite=mouse, group=self.all_sprites, dokill=False)

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

    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        mouse = MousePointer(pos=event.pos)

        sprites = pygame.sprite.spritecollide(sprite=mouse, group=self.all_sprites, dokill=False)

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


class MenuItem(BitmappySprite):
    """A menu item class.

    This class represents a menu item.  It can be a root level menu item or a sub menu item.

    Args:
        BitmappySprite (BitmappySprite): The base sprite class.

    Returns:
        None
    """
    log = LOG

    def __init__(self: Self, x: int = 0, y: int = 0, width: int = 1, height: int = 1,
                 name: str | None = None, filename: str | None = None, parent: object | None = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize a MenuItem.

        Args:
            x (int): The x coordinate of the menu item.
            y (int): The y coordinate of the menu item.
            width (int): The width of the menu item.
            height (int): The height of the menu item.
            name (str | None): The name of the menu item.
            filename (str | None): The filename of the menu item.
            parent (object | None): The parent of the menu item.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

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

    def add(self: Self, *groups: pygame.sprite.LayeredDirty) -> None:
        """Add the sprite to a group.

        Args:
            *groups (pygame.sprite.LayeredDirty): The groups to add the sprite to.

        Returns:
            None
        """
        # super().add(*groups)

        # There's something funky with MRO and pygame
        # doing things this way avoids dirtier tricks.
        try:
            text = getattr(self, 'text')  # noqa: B009
            text.add(*groups)
        except AttributeError:
            pass

    def add_menu(self: Self, menu: MenuItem) -> None:
        """Add a menu to the menu item.

        Args:
            menu (MenuItem): The menu to add.

        Returns:
            None
        """
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

    def add_menu_item(self: Self, menu_item: MenuItem, menu: MenuBar) -> None:
        """Add a menu item to the menu item.

        Args:
            menu_item (MenuItem): The menu item to add.
            menu (MenuBar): The menu to add the menu item to.

        Returns:
            None
        """
        if menu is None:
            self.add_menu(menu=menu_item)
            self.log.debug(f'{type(self)} Adding new menu {menu_item}.')
        else:
            self.log.debug(f'{type(self)} Adding menu item {menu_item} to menu {menu}.')

    def update(self: Self) -> None:
        """Update the menu item.

        Args:
            None

        Returns:
            None
        """
        # self.log.debug(f'Menu Items: {self.menu_items.items()}')
        self.screen.blit(self.image, (self.rect.x, self.rect.y))

        if self.active and self.menu_image and self.menu_rect:
            self.log.debug('Trying to draw the menu')
            pygame.display.get_surface().blit(self.menu_image,
                                                (self.menu_rect.x, self.menu_rect.y))

    def on_mouse_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse,
            group=self.all_sprites,
            dokill=False
        )

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

    def on_mouse_enter_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse enter events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} ENTER MENU {self.name}')
        # Figure out which item was entered.
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse,
            group=self.all_sprites,
            dokill=False
        )

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

    def on_mouse_exit_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse exit events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Figure out which item was entered.
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse,
            group=self.all_sprites,
            dokill=False
        )

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

    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Up {self.name}')
        self.image = self.menu_up_image
        self.rect = self.menu_up_rect
        self.active = 0
        self.dirty = 2
        self.update()

        # Figure out which item was clicked.
        mouse = MousePointer(pos=event.pos)

        self.log.debug(f'Process MOUSE UP {event} at {mouse}')

        sprites = pygame.sprite.spritecollide(
            sprite=mouse,
            group=self.all_sprites,
            dokill=False
        )

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

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Down {self.name}')
        self.image = self.menu_down_image
        self.rect = self.menu_down_rect
        self.active = 1
        self.dirty = 2

        self.update()

        # Figure out which item was clicked.
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse,
            group=self.all_sprites,
            dokill=False
        )

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


class TextSprite(BitmappySprite):
    """A text sprite class."""
    log = LOG

    class TextBox(Sprite):
        """A text box class."""
        log = LOG

        def __init__(self: Self, font: str, x: int, y: int, line_height: int = 15,
                     text: str = 'Text', text_color: tuple = WHITE, parent: object = None,
                     groups: pygame.sprite.LayeredDirty | None = None) -> None:
            """Initialize a TextBox.

            Args:
                font (str): The font to use.
                x (int): The x coordinate of the text box.
                y (int): The y coordinate of the text box.
                line_height (int): The line height of the text box.
                text (str): The text to display in the text box.
                text_color (tuple): The color of the text.
                parent (object): The parent object.
                groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

            Returns:
                None
            """
            if groups is None:
                groups = pygame.sprite.LayeredDirty()

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

        def print_text(self: Self, surface: pygame.surface.Surface, string: str) -> None:
            """Print text to the text box.

            Args:
                surface (pygame.surface.Surface): The surface to print the text to.
                string (str): The text to print.

            Returns:
                None
            """
            (self.image, self.rect) = self.font.render(string, fgcolor=self.active_text_color)
            # , bgcolor=self.active_background_color)
            self.image.set_colorkey((255, 0, 255))
            self.image.convert()

            self.rect.centerx = self.x
            self.rect.centery = self.y
            self.y += self.line_height
            self.dirty = 1

        def reset(self: Self) -> None:
            """Reset the text box.

            Args:
                None

            Returns:
                None
            """
            self.x = self.start_x
            self.y = self.start_y
            self.dirty = 1

        def indent(self: Self) -> None:
            """Indent the text box.

            Args:
                None

            Returns:
                None
            """
            self.x += 10
            self.dirty = 1

        def unindent(self: Self) -> None:
            """Unindent the text box.

            Args:
                None

            Returns:
                None
            """
            self.x -= 10
            self.dirty = 1

        @property
        def x(self: Self) -> int:
            """Get the x coordinate of the text box.

            Args:
                None

            Returns:
                int: The x coordinate of the text box.
            """
            return self.start_x

        @x.setter
        def x(self: Self, new_x: int) -> None:
            """Set the x coordinate of the text box.

            Args:
                new_x (int): The new x coordinate of the text box.

            Returns:
                None
            """
            self.rect.x = self.parent.rect.centerx if self.parent else new_x
            self.start_x = self.rect.x
            # self.slider_knob.rect.centerx = self.rect.x + self.slider_knob.value
            # self.text_sprite.x = 240
            # self.text_sprite.text_box.x = self.parent.rect.centerx \
            #     if self.parent else self.rect.centerx
            self.dirty = 1

        @property
        def y(self: Self) -> int:
            """Get the y coordinate of the text box.

            Args:
                None

            Returns:
                int: The y coordinate of the text box.
            """
            return self.start_y

        @y.setter
        def y(self: Self, new_y: int) -> None:
            """Set the y coordinate of the text box.

            Args:
                new_y (int): The new y coordinate of the text box.

            Returns:
                None
            """
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

        # def on_mouse_unfocus_event(self: Self, event: pygame.event.Event) -> None:
        #     self.active_text_color = self.text_color
        #     self.active_background_color = self.background_color

        # def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        #     self.active_text_color = self.text_click_color
        #     self.active_background_color = self.background_click_color

        # def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        #     self.active_text_color = self.text_hover_color
        #     self.active_background_color = self.background_hover_color

    def __init__(self: Self, x: int, y: int, width: int, height: int, name: str | None = None,
                 background_color: tuple = BLACKLUCENT, text_color: tuple = WHITE,
                 alpha: int = 0, text: str = 'Text', parent: object | None = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize a TextSprite.

        Args:
            x (int): The x coordinate of the text sprite.
            y (int): The y coordinate of the text sprite.
            width (int): The width of the text sprite.
            height (int): The height of the text sprite.
            name (str): The name of the text sprite.
            background_color (tuple): The background color of the text sprite.
            text_color (tuple): The color of the text.
            alpha (int): The alpha value of the text sprite.
            text (str): The text to display in the text sprite.
            parent (object): The parent object.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

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
            # way to get a translucent image which
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
    def x(self: Self) -> int:
        """Get the x coordinate of the text sprite.

        Args:
            None

        Returns:
            int: The x coordinate of the text sprite.
        """
        return self.rect.x

    @x.setter
    def x(self: Self, new_x: int) -> None:
        """Set the x coordinate of the text sprite.

        Args:
            new_x (int): The new x coordinate of the text sprite.

        Returns:
            None
        """
        self.rect.x = new_x
        self.text_box.start_x = self.parent.rect.centerx if self.parent else new_x
        # self.text_box.start_x = self.x
        self.dirty = 1

    @property
    def y(self: Self) -> int:
        """Get the y coordinate of the text sprite.

        Args:
            None

        Returns:
            int: The y coordinate of the text sprite.
        """
        return self.rect.y

    @y.setter
    def y(self: Self, new_y: int) -> None:
        """Set the y coordinate of the text sprite.

        Args:
            new_y (int): The new y coordinate of the text sprite.

        Returns:
            None
        """
        self.rect.y = new_y
        self.text_box.start_y = self.parent.rect.centery if self.parent else new_y
        # self.text_box.start_y = self.y
        self.dirty = 1

    def update_nested_sprites(self: Self) -> None:
        """Update the nested sprites.

        Args:
            None

        Returns:
            None
        """
        self.text_box.dirty = self.dirty

    def update(self: Self) -> None:
        """Update the text sprite.

        Args:
            None

        Returns:
            None
        """
        self.image.fill(self.active_color)

        self.text_box.reset()
        self.text_box.print_text(self.image, f'{self.text}')

    def add(self: Self, *groups: pygame.sprite.LayeredDirty) -> None:
        """Add the sprite to a group.

        Args:
            *groups (pygame.sprite.LayeredDirty): The groups to add the sprite to.

        Returns:
            None
        """
        super().add(*groups)

        # There's something funky with MRO and pygame
        # doing things this way avoids dirtier tricks.
        try:
            text_box = getattr(self, 'text_box')  # noqa: B009
            text_box.add(*groups)
        except AttributeError:
            pass

    def on_mouse_focus_event(self: Self, event: pygame.event.Event, focus: object) -> None:
        """Handle mouse focus events.

        Args:
            event (pygame.event.Event): The event to handle.
            focus (object): The object that has focus.

        Returns:
            None
        """
        self.active_color = self.hover_color
        self.dirty = 1

    def on_mouse_unfocus_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse unfocus events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.active_color = self.background_color
        self.dirty = 1

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.active_color = self.click_color
        self.dirty = 1

    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.active_color = self.background_color
        self.dirty = 1


class ButtonSprite(BitmappySprite):
    """A button sprite class."""

    log = LOG

    def __init__(self: Self, x: int, y: int, width: int, height: int, name: str | None = None,
                 parent: object | None = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize a ButtonSprite.

        Args:
            x (int): The x coordinate of the button sprite.
            y (int): The y coordinate of the button sprite.
            width (int): The width of the button sprite.
            height (int): The height of the button sprite.
            name (str): The name of the button sprite.
            parent (object): The parent object.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

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
    def x(self: Self) -> int:
        """Get the x coordinate of the button sprite.

        Args:
            None

        Returns:
            int: The x coordinate of the button sprite.
        """
        return self.rect.x

    @x.setter
    def x(self: Self, new_x: int) -> None:
        """Set the x coordinate of the button sprite.

        Args:
            new_x (int): The new x coordinate of the button sprite.

        Returns:
            None
        """
        self.rect.x = new_x
        self.text.x = self.parent.rect.centerx if self.parent else new_x
        self.dirty = 1

    @property
    def y(self: Self) -> int:
        """Get the y coordinate of the button sprite.

        Args:
            None

        Returns:
            int: The y coordinate of the button sprite.
        """
        return self.rect.y

    @y.setter
    def y(self: Self, new_y: int) -> None:
        """Set the y coordinate of the button sprite.

        Args:
            new_y (int): The new y coordinate of the button sprite.

        Returns:
            None
        """
        self.rect.y = new_y
        self.text.y = self.parent.rect.centery if self.parent else new_y
        self.dirty = 1

    def update_nested_sprites(self: Self) -> None:
        """Update the nested sprites.

        Sets the dirty flag on the nested sprites.

        Args:
            None

        Returns:
            None
        """
        self.text.dirty = self.dirty

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.background_color = self.active_color
        # self.update()
        super().on_left_mouse_button_down_event(event)
        self.dirty = 1

    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.background_color = self.inactive_color
        # self.update()
        super().on_left_mouse_button_up_event(event)
        self.dirty = 1


class CheckboxSprite(ButtonSprite):
    """A checkbox sprite class."""

    log = LOG

    def __init__(self: Self, x: int, y: int, width: int, height: int, name: str | None = None,
                 callbacks: Callable | None = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize a CheckboxSprite.

        Args:
            x (int): The x coordinate of the checkbox sprite.
            y (int): The y coordinate of the checkbox sprite.
            width (int): The width of the checkbox sprite.
            height (int): The height of the checkbox sprite.
            name (str): The name of the checkbox sprite.
            callbacks (Callable): The callbacks to call when events occur.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(x=x, y=y, width=width, height=height, name=name,
                         groups=groups)

        self.checked = False
        self.color = (128, 128, 128)

    def update(self: Self) -> None:
        """Update the checkbox sprite.

        Args:
            None

        Returns:
            None
        """
        if not self.checked:
            self.image.fill((0, 0, 0))

        pygame.draw.rect(self.image, self.color, Rect(0, 0, self.width, self.height), 1)

        if self.checked:
            pygame.draw.line(self.image, self.color, (0, 0), (self.width - 1, self.height - 1), 1)
            pygame.draw.line(self.image, self.color, (0, self.height - 1), (self.width - 1, 0), 1)

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """

    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.checked = not self.checked
        # self.update()
        self.dirty = 1


class InputBox(Sprite):
    """An input box class."""

    def __init__(self: Self, x: int, y: int, width: int, height: int, color: tuple=(233, 248, 215),
                 text: str = '', name: str | None = None, parent: object | None = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize an InputBox.

        Args:
            x (int): The x coordinate of the input box.
            y (int): The y coordinate of the input box.
            width (int): The width of the input box.
            height (int): The height of the input box.
            color (tuple): The color of the input box.
            text (str): The text to display in the input box.
            name (str): The name of the input box.
            parent (object): The parent object.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)
        pygame.font.init()
        self.offset_x = self.parent.x if self.parent else 0
        self.offset_y = self.parent.y if self.parent else 0
        self.rect.x = x + self.offset_x
        self.rect.y = y + self.offset_y
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.font = pygame.font.SysFont('Times', 14)
        self.text = text
        self.text_image = self.font.render(self.text, True, self.color) # noqa: FBT003
        self.active = False
        self.image = pygame.Surface((self.width, self.height))
        self.image.convert()
        self.parent = parent

        self.cursor_rect = self.text_image.get_rect()

        self.cursor = pygame.Rect(
            self.cursor_rect.topright,
            (3, self.cursor_rect.height)
        )

        self.dirty = 2

    def activate(self: Self) -> None:
        """Activate the input box.

        Args:
            None

        Returns:
            None
        """
        self.active = True
        self.dirty = 2

    def deactivate(self: Self) -> None:
        """Deactivate the input box.

        Args:
            None

        Returns:
            None
        """
        self.active = False
        self.dirty = 0

    def on_input_box_submit_event(self: Self, event: pygame.event.Event) -> None:
        """Handle input box submit events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        if self.parent:
            try:
                self.parent.on_input_box_submit_event(event=self)
            except AttributeError:
                self.log.info(f'{self.name}: Submitted "{self.text}" but no parent is configured.')

    def update(self: Self) -> None:
        """Update the input box.

        Args:
            None

        Returns:
            None
        """
        self.image.fill((0, 0, 0))
        self.image.blit(self.text_image, (4, 4))

        pygame.draw.rect(self.image, self.color, (0, 0, self.rect.width, self.rect.height), 1)

        # Blit the  cursor
        if time.time() % 1 > 0.5 and self.active:  # noqa: PLR2004
            self.cursor_rect = self.text_image.get_rect(topleft=(5, 2))

            self.cursor.midleft = self.cursor_rect.midright

            pygame.draw.rect(self.image, self.color, self.cursor)

    def render(self: Self) -> None:
        """Render the input box.

        Args:
            None

        Returns:
            None
        """
        self.text_image = self.font.render(self.text, True, (255, 255, 255))  # noqa: FBT003

    def on_mouse_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.activate()

    def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.info(f'INPUT BOX EVENT: {event}')
        if self.active:
            pygame.key.set_repeat(200)

            if event.key in (pygame.K_TAB, pygame.K_ESCAPE):
                self.deactivate()

    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        if self.active:
            if event.key in (pygame.K_TAB, pygame.K_ESCAPE):
                pass
            elif event.key == pygame.K_RETURN:
                self.log.debug(f'Text Submitted: {self.name}: {self.text}')
                self.on_input_box_submit_event(event=self)
                self.text = ''
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                self.text += event.unicode

                self.cursor_rect.size = self.text_image.get_size()
                self.cursor.topleft = self.cursor_rect.topright

                if self.text_image.get_width() > self.rect.width - 15:
                    self.text = self.text[:-1]
            self.render()
            self.log.debug(f'{self.name}: {self.text}')


class TextBoxSprite(BitmappySprite):
    """A text box sprite class."""

    log = LOG

    def __init__(self: Self, x: int, y: int, width: int, height: int, name: str | None = None,
                 callbacks: Callable | None = None, parent: object | None = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize a TextBoxSprite.

        Args:
            x (int): The x coordinate of the text box sprite.
            y (int): The y coordinate of the text box sprite.
            width (int): The width of the text box sprite.
            height (int): The height of the text box sprite.
            name (str): The name of the text box sprite.
            callbacks (Callable): The callbacks to call when events occur.
            parent (object): The parent object.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

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

    def update_nested_sprites(self: Self) -> None:
        """Update the nested sprites.

        Args:
            None

        Returns:
            None
        """
        self.text_box.dirty = self.dirty

    def update(self: Self) -> None:
        """Update the text box sprite.

        Args:
            None

        Returns:
            None
        """
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

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.background_color = (128, 128, 128)
        self.dirty = 1

    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.background_color = (0, 0, 0)
        self.dirty = 1


class SliderSprite(BitmappySprite):
    """A slider sprite class."""

    log = LOG

    class SliderKnobSprite(BitmappySprite):
        """A slider knob sprite class."""
        log = LOG

        def __init__(self: Self, x: int, y: int, width: int, height: int, name: str | None = None,
                     parent: object | None = None,
                     groups: pygame.sprite.LayeredDirty | None = None) -> None:
            """Initialize a SliderKnobSprite.

            Args:
                x (int): The x coordinate of the slider knob sprite.
                y (int): The y coordinate of the slider knob sprite.
                width (int): The width of the slider knob sprite.
                height (int): The height of the slider knob sprite.
                name (str): The name of the slider knob sprite.
                parent (object): The parent object.
                groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

            Returns:
                None
            """
            if groups is None:
                groups = pygame.sprite.LayeredDirty()

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

        def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
            """Handle left mouse button down events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None
            """
            self.dirty = 1
            self.value = event.pos[0] - self.parent.x

            # Clamp to 8-bit
            if self.value > 255:  # noqa: PLR2004
                self.value = 255
            elif self.value < 0:
                self.value = 0

            self.rect.centerx = self.parent.x + self.value if self.parent else self.x + self.value
            super().on_left_mouse_button_down_event(event)

        def on_left_mouse_drag_event(self: Self, event: pygame.event.Event,
                                     trigger: object) -> None:
            """Handle left mouse drag events.

            Args:
                event (pygame.event.Event): The event to handle.
                trigger (object): The object that triggered the event.

            Returns:
                None
            """
            # There's not a good way to pass any useful info, so for now, pass None
            # since we're not using the event for anything in this class.
            self.on_left_mouse_button_down_event(event)
            self.dirty = 1

    def __init__(self: Self, x: int, y: int, width: int, height: int, name: str | None = None,
                 parent: object | None = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize a SliderSprite.

        Args:
            x (int): The x coordinate of the slider sprite.
            y (int): The y coordinate of the slider sprite.
            width (int): The width of the slider sprite.
            height (int): The height of the slider sprite.
            name (str): The name of the slider sprite.
            parent (object): The parent object.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

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
    def value(self: Self) -> int:
        """Get the value of the slider sprite.

        Args:
            None

        Returns:
            int: The value of the slider sprite.
        """
        return self.slider_knob.value

    @value.setter
    def value(self: Self, value: int) -> None:
        """Set the value of the slider sprite.

        Args:
            value (int): The new value of the slider sprite.

        Returns:
            None
        """
        self.slider_knob.value = value

    @property
    def x(self: Self) -> int:
        """Get the x coordinate of the slider sprite.

        Args:
            None

        Returns:
            int: The x coordinate of the slider sprite.
        """
        return self.rect.x

    @x.setter
    def x(self: Self, new_x: int) -> None:
        """Set the x coordinate of the slider sprite.

        Args:
            new_x (int): The new x coordinate of the slider sprite.

        Returns:
            None
        """
        self.rect.x = new_x
        self.slider_knob.rect.centerx = self.rect.x + self.slider_knob.value
        self.text_sprite.x = 240
        # self.text_sprite.text_box.x = self.parent.rect.centerx \
        #     if self.parent else self.rect.centerx
        self.dirty = 1

    @property
    def y(self: Self) -> int:
        """Get the y coordinate of the slider sprite.

        Args:
            None

        Returns:
            int: The y coordinate of the slider sprite.
        """
        return self.rect.y

    @y.setter
    def y(self: Self, new_y: int) -> None:
        """Set the y coordinate of the slider sprite.

        Args:
            new_y (int): The new y coordinate of the slider sprite.

        Returns:
            None
        """
        self.rect.y = new_y
        self.text_sprite.y = self.parent.rect.y if self.parent else self.rect.y
        # self.text_sprite.text_box.y = self.parent.rect.centery \
        #     if self.parent else self.rect.centery

        self.dirty = 1

    def update_nested_sprites(self: Self) -> None:
        """Update the nested sprites.

        Args:
            None

        Returns:
            None
        """
        self.slider_knob.dirty = self.dirty
        self.text_sprite.dirty = self.dirty
        # self.text_sprite.text.dirty = self.dirty

    def update(self: Self) -> None:
        """Update the slider sprite.

        Args:
            None

        Returns:
            None
        """
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

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.slider_knob.on_left_mouse_button_down_event(event)
        super().on_left_mouse_button_down_event(event)
        self.dirty = 1

    def on_left_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle left mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        self.on_left_mouse_button_down_event(event)
        # There's not a good way to pass any useful info, so for now, pass None
        # since we're not using the event for anything in this class.
        self.slider_knob.on_left_mouse_drag_event(event, trigger)
        super().on_left_mouse_drag_event(event, trigger)
        self.dirty = 1


class ColorWellSprite(BitmappySprite):
    """A color well sprite class."""
    log = LOG

    def __init__(self: Self, x: int, y: int, width: int, height: int, name: str,
                 parent: object | None = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize a ColorWellSprite.

        Args:
            x (int): The x coordinate of the color well sprite.
            y (int): The y coordinate of the color well sprite.
            width (int): The width of the color well sprite.
            height (int): The height of the color well sprite.
            name (str): The name of the color well sprite.
            parent (object): The parent object.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

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
    def active_color(self: Self) -> tuple[int, int, int]:
        """Get the active color.

        Args:
            None

        Returns:
            tuple[R: int, G: int, B: int]: The active color.
        """
        return (self.red, self.green, self.blue)

    @active_color.setter
    def active_color(self: Self, active_color: tuple[int, int, int]) -> None:
        """Set the active color.

        Args:
            active_color (tuple[R: int, G: int, B: int]): The new active color.

        Returns:
            None
        """
        self.red = active_color[0]
        self.green = active_color[1]
        self.blue = active_color[2]
        self.dirty = 1

    @property
    def hex_color(self: Self) -> str:
        """Get the hex color.

        Args:
            None

        Returns:
            str: The hex color in #RRGGBB format.
        """
        hex_str = '{:02X}'
        red, green, blue = self.active_color

        red = hex_str.format(red)
        green = hex_str.format(green)
        blue = hex_str.format(blue)

        return f'#{red}{green}{blue}'

    def update_nested_sprites(self: Self) -> None:
        """Update the nested sprites.

        Args:
            None

        Returns:
            None
        """
        self.text_sprite.dirty = 1

    def update(self: Self) -> None:
        """Update the color well sprite.

        Args:
            None

        Returns:
            None
        """
        pygame.draw.rect(self.image, (128, 128, 255), Rect(0, 0, self.width, self.height), 1)
        pygame.draw.rect(self.image, self.active_color, Rect(1, 1, self.width - 2, self.height - 2))

        self.text_sprite.value = str(self.active_color)
        self.text_sprite.text_box.text = self.hex_color
        self.text_sprite.dirty = 1


class InputDialog(BitmappySprite):
    """An input dialog class."""

    log = LOG

    def __init__(self: Self, x: int, y: int, width: int, height: int, name: str | None =None,
                 dialog_text: str = 'Would you like to do a thing?',
                 confirm_text: str = 'Confirm', cancel_text: str = 'Cancel',
                 callbacks: Callable | None = None, parent: object = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize an InputDialog.

        Args:
            x (int): The x coordinate of the input dialog.
            y (int): The y coordinate of the input dialog.
            width (int): The width of the input dialog.
            height (int): The height of the input dialog.
            name (str): The name of the input dialog.
            dialog_text (str): The text to display in the dialog.
            confirm_text (str): The text to display on the confirm button.
            cancel_text (str): The text to display on the cancel button.
            callbacks (Callable): The callbacks to call when events occur.
            parent (object): The parent object.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(x=x, y=y, width=width, height=height, name=name, parent=parent,
                         groups=groups)
        self.background_color = (0, 0, 0)
        self.border_width = 1
        self.width = width
        self.rect.x = x
        self.rect.y = y

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

        self.input_box = InputBox(
            x=self.rect.x + self.rect.width // 2,
            y=self.rect.y + self.rect.height // 2,
            width=200,
            height=20,
            text='',
            parent=self,
            groups=groups
        )

        self.input_box.rect.x -= self.input_box.width // 2

        self.input_box.activate()

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
        # self.input_box.x = self.input_box.width // 2
        # self.input_box.y = self.input_box.rect.y
        # self.confirm_button.update_nested_sprites()

    def update_nested_sprites(self: Self) -> None:
        """Update the nested sprites.

        Args:
            None

        Returns:
            None
        """
        self.cancel_button.dirty = self.dirty
        self.confirm_button.dirty = self.dirty

    def update(self: Self) -> None:
        """Update the input dialog.

        Args:
            None

        Returns:
            None
        """
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

        self.screen.blit(
            self.input_box.image,
            (self.input_box.rect.x, self.input_box.rect.y)
        )

    def on_confirm_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle confirm events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        if self.parent:
            self.parent.on_confirm_event(event=event, trigger=trigger)
        self.log.info(f'{self.name}: Got confirm event!')

    def on_cancel_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle cancel events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        if self.parent:
            self.parent.on_cancel_event(event=event, trigger=trigger)
        self.log.info(f'{self.name}: Got cancel event!')

    def on_input_box_cancel_event(self: Self, control: object) -> None:
        """Handle input box cancel events.

        Args:
            control (object): The control that triggered the event.

        Returns:
            None
        """
        self.log.info(f'{self.name} Got text input from: {control.name}: {control.text}')
        self.on_cancel_event(event=control, trigger=control)

    def on_input_box_submit_event(self: Self, event: pygame.event.Event) -> None:
        """Handle input box submit events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.info(f'{self.name} Got text input from: {event.name}: {event.text}')
        self.on_confirm_event(event=event, trigger=event)

    def on_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{self.name} Got mouse button up event: {event}')
        self.input_box.activate()

    def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.info(f'Got Event: {event} from {self.parent}')

        if self.input_box.active:
            self.input_box.on_key_up_event(event)
        elif event.key == pygame.K_TAB:
            self.input_box.activate()
        else:
            super().on_key_up_event(event)

    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        if self.input_box.active:
            self.input_box.on_key_down_event(event)
        else:
            super().on_key_up_event(event)

        # Draw the buttons
        # Draw the text input field
