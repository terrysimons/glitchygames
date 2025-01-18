#!/usr/bin/env python3
"""GlitchyGames UI classes."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Self

import pygame
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
from pygame import Rect

if TYPE_CHECKING:
    from collections.abc import Callable

LOG = logging.getLogger('game.ui')
LOG.addHandler(logging.NullHandler())


class MenuBar(FocusableSingletonBitmappySprite):
    """A menu bar class."""

    log = LOG

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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

        # Create surface with alpha support
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.image = self.image.convert_alpha()

        # Create RGBA colors
        menu_bg_color = (WHITE[0], WHITE[1], WHITE[2], 128)  # Semi-transparent white
        border_color = (WHITE[0], WHITE[1], WHITE[2], 128)   # Semi-transparent white

        # Draw with alpha
        pygame.draw.rect(self.image, menu_bg_color, self.rect)
        pygame.draw.rect(self.image, border_color, self.rect, self.border_width)

        # Always refresh the menu bar.
        self.dirty = 2

    def add_menu(self: Self, menu: MenuItem) -> None:
        """Add a menu to the menu bar."""
        self.menu_items[menu.name] = menu
        self.log.info(f'Before offset: menu {menu.name} at x={menu.rect.x}, offset={self.menu_offset_x}')
        menu.image.set_colorkey((255, 0, 255))
        menu.add(self.groups())

        # Store original position before any adjustments
        original_x = menu.rect.x

        # Only adjust if this isn't the first menu item
        if self.menu_offset_x > self.border_width:
            menu.rect.x = self.menu_offset_x
            # Only adjust text position if it exists
            if hasattr(menu, 'text'):
                menu.text.rect.x = self.menu_offset_x

        menu.rect.y += self.menu_offset_y
        # Only adjust text y position if it exists
        if hasattr(menu, 'text'):
            menu.text.rect.y += self.menu_offset_y

        self.log.info(f'After offset: menu {menu.name} at x={menu.rect.x}')
        self.menu_offset_x = menu.rect.x + menu.rect.width + self.border_width
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
            # Blit with alpha support
            self.image.blit(menu_item.image, (menu_item.rect.x, menu_item.rect.y))

        if self.has_focus:
            focus_color = (WHITE[0], WHITE[1], WHITE[2], 128)
            pygame.draw.rect(self.image, focus_color, self.rect, 1)

    def on_left_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle left mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drag {event} @ {self} for {trigger}')

    def on_left_mouse_drop_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drop {self.name}')

    def on_middle_mouse_drag_event(self: Self, event: pygame.event.Event) -> None:
        """Handle middle mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drag {self.name}')

    def on_middle_mouse_drop_event(self: Self, event: pygame.event.Event) -> None:
        """Handle middle mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drop {self.name}')

    def on_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drag {self.name}')

    def on_mouse_drop_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drop {self.name}')

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
            sprite=mouse, group=self.all_sprites, dokill=False
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
            sprite=mouse, group=self.all_sprites, dokill=False
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
                self.log.debug(
                    f'{type(self)} {self.name} ' f'Mouse button up on {self.name} at {mouse}'
                )
                sprite.on_left_mouse_button_down_event(event)

                for menu_item in sprite.menu_items:
                    sprite.menu_items[menu_item].on_left_mouse_button_up_event(event)

    def on_right_mouse_drag_event(self: Self, event: pygame.event.Event) -> None:
        """Handle right mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drag {self.name}')

    def on_right_mouse_drop_event(self: Self, event: pygame.event.Event) -> None:
        """Handle right mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drop {self.name}')

    def on_mouse_wheel_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse wheel events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Wheel {self.name}')


class MenuItem(BitmappySprite):
    """A menu item class.

    This class represents a menu item.  It can be a root level menu item or a sub menu item.

    Args:
        BitmappySprite (BitmappySprite): The base sprite class.

    Returns:
        None
    """

    log = LOG

    def __init__(
        self: Self,
        x: int = 0,
        y: int = 0,
        width: int = 1,
        height: int = 1,
        name: str | None = None,
        filename: str | None = None,
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            focusable=True,
            filename=filename,
            groups=groups,
        )
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
                x=x,
                y=y,
                width=self.width,
                height=self.height,
                text=self.name,
                parent=parent,
                groups=groups,
            )
            self.text.image.set_colorkey((255, 0, 255))
            self.text.add(groups)
            # Align the rect with the text position
            self.rect.x = self.text.rect.x
            self.rect.y = self.text.rect.y

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

        width = (
            max([self.menu_items[menu_item].rect.width + 20 for menu_item in self.menu_items]) * 2.5
        )
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
        """Update the menu item."""
        # Draw to our own surface instead of the screen
        if self.active and self.menu_image and self.menu_rect:
            self.log.debug('Drawing the menu')
            self.image.blit(self.menu_image, (0, 0))  # Draw relative to our own surface

    def on_left_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle left mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The trigger object.
        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drag {self.name}')

    def on_left_mouse_drop_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle left mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drop {self.name}')

    def on_middle_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle middle mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drag {self.name}')

    def on_middle_mouse_drop_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle middle mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drop {self.name}')

    def on_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drag {self.name}')

    def on_mouse_drop_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drop {self.name}')

    def on_mouse_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse, group=self.all_sprites, dokill=False
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
            sprite=mouse, group=self.all_sprites, dokill=False
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
            sprite=mouse, group=self.all_sprites, dokill=False
        )

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.debug(
                    f'Mouse exit on {collided_sprite.name} ' f'{collided_sprite.rect} at {mouse}'
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

        sprites = pygame.sprite.spritecollide(sprite=mouse, group=self.all_sprites, dokill=False)

        for sprite in sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            # if sprite.name in self.menu_items:
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
                    pygame.event.Event(events.MENUEVENT, {'menu': self, 'menu_item': sprite})
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
            sprite=mouse, group=self.all_sprites, dokill=False
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

    def on_right_mouse_drag_event(self: Self, event: pygame.event.Event) -> None:
        """Handle right mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drag {self.name}')

    def on_right_mouse_drop_event(self: Self, event: pygame.event.Event) -> None:
        """Handle right mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Drop {self.name}')

    def on_mouse_wheel_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse wheel events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} Mouse Wheel {self.name}')


class TextSprite(BitmappySprite):
    """A text sprite class."""

    log = LOG

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str | None = None,
        background_color: tuple = (255, 0, 255),
        text_color: tuple = WHITE,
        alpha: int = 0,
        text: str = 'Text',
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            focusable=True,
            groups=groups,
        )

        # Store coordinates
        self._x = x
        self._y = y
        self.background_color = background_color
        self.text_color = text_color
        self.alpha = alpha
        self._text = text
        self.parent = parent
        self.all_sprites = groups

        # Make this instance also act as its own text_box for compatibility
        self.text_box = self

        self.update_text(text)

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value):
        self._x = value
        self.rect.x = value
        self.dirty = 2

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, value):
        self._y = value
        self.rect.y = value
        self.dirty = 2

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        if value != self._text:  # Only update if text has changed
            self._text = str(value)
            self.update_text(self._text)
            self.dirty = 2

    def update(self):
        """Update the sprite."""
        if self.dirty:
            self.update_text(self._text)

    def update_text(self, text):
        """Update the text surface."""
        # Create surface with alpha support
        self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.image = self.image.convert_alpha()

        # Fill with black background (or any color that contrasts with the text)
        self.image.fill((0, 0, 0, 0))  # Fully transparent black

        # Create text surface using pygame's default font with no anti-aliasing
        font = pygame.font.Font(None, 24)
        text_surface = font.render(str(text), False, self.text_color)  # False = no anti-aliasing

        # Position the text in the center of our surface
        text_rect = text_surface.get_rect()
        target_rect = self.image.get_rect()
        text_rect.centerx = target_rect.centerx
        text_rect.centery = target_rect.centery

        # Blit text onto our surface
        self.image.blit(text_surface, text_rect)


class ButtonSprite(BitmappySprite):
    """A button sprite class."""

    log = LOG

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str | None = None,
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            focusable=True,
            parent=parent,
            groups=groups,
        )
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
            groups=groups,
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
        self.text.x = new_x  # Position relative to button
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
        self.text.y = new_y  # Position relative to button
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

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str | None = None,
        callbacks: Callable | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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

        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)

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

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: tuple = (233, 248, 215),
        text: str = '',
        name: str | None = None,
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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
        self.text_image = self.font.render(self.text, True, self.color)  # noqa: FBT003
        self.active = False
        self.image = pygame.Surface((self.width, self.height))
        self.image.convert()
        self.parent = parent

        self.cursor_rect = self.text_image.get_rect()

        self.cursor = pygame.Rect(self.cursor_rect.topright, (3, self.cursor_rect.height))

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

            if event.key in {pygame.K_TAB, pygame.K_ESCAPE}:
                self.deactivate()

    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key down events."""
        if self.active:
            if event.key == pygame.K_RETURN:
                # Trigger confirm button instead of adding newline
                if hasattr(self.parent, 'on_confirm_event'):
                    self.parent.on_confirm_event(event=event, trigger=self)
            else:
                # Handle other key input
                if event.key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]
                else:
                    self.text += event.unicode
                self.render()


class TextBoxSprite(BitmappySprite):
    """A text box sprite class."""

    log = LOG

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str | None = None,
        callbacks: Callable | None = None,
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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
            x=x, y=y, width=width, height=height, name=name, parent=parent, groups=groups
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
            groups=groups,
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
                self.image, (128, 128, 128), Rect(0, 0, self.width, self.height), self.border_width
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

    log = logging.getLogger('game')

    class SliderKnobSprite(BitmappySprite):
        """A slider knob sprite class."""

        log = logging.getLogger('game')

        def __init__(
            self: Self,
            x: int,
            y: int,
            width: int,
            height: int,
            name: str | None = None,
            parent: object | None = None,
            groups: pygame.sprite.LayeredDirty | None = None,
        ) -> None:
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
                x=x, y=y, width=width, height=height, name=name, parent=parent, groups=groups
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

        def on_left_mouse_drag_event(
            self: Self, event: pygame.event.Event, trigger: object
        ) -> None:
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

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int = 256,
        height: int = 9,
        name: str | None = None,
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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

        # Store parent in a temporary variable
        self._temp_parent = parent

        self.log = logging.getLogger('game')
        self.log.info(f"Initializing slider {name} with parent {parent}")

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            focusable=True,
            groups=groups,
        )

        # Force set parent after super init
        self.parent = self._temp_parent
        delattr(self, '_temp_parent')

        self.log.info(f"After super().__init__, parent is now {self.parent}")

        # Initialize base values
        self._value = 0
        self.min_x = x
        self.max_x = x + width - 5
        self.dragging = False

        # Initialize the slider knob
        self.slider_knob = BitmappySprite(
            x=x,
            y=y,
            width=5,
            height=height,
            name=f'{name}_knob',
            groups=groups,
        )
        self.slider_knob.image.fill((200, 200, 200))

        # Create the text sprite
        text_x = x + width + 10
        self.text_sprite = TextSprite(
            x=text_x,
            y=y - (height // 2),
            width=32,
            height=20,
            text='0',
            groups=groups,
        )

        # Set color based on slider name
        if name == 'R':
            self.color = (255, 0, 0)
        elif name == 'G':
            self.color = (0, 255, 0)
        elif name == 'B':
            self.color = (0, 0, 255)
        else:
            self.color = (128, 128, 128)

        # Set up appearance
        self.update_slider_appearance()

        # Create the text sprite
        text_x = x + width + 10
        self.text_sprite = TextSprite(
            x=text_x,
            y=y - (height // 2),
            width=32,
            height=20,
            text='0',
            groups=groups,
        )

        # Set color based on slider name
        if name == 'R':
            self.color = (255, 0, 0)
        elif name == 'G':
            self.color = (0, 255, 0)
        elif name == 'B':
            self.color = (0, 0, 255)
        else:
            self.color = (128, 128, 128)

        # Set up appearance
        self.update_slider_appearance()

        # Make sure we update
        self.dirty = 2
        self.slider_knob.dirty = 2

        # Now set the initial value
        self.value = self._value

        self.log.info(f"Finished initializing slider {name}, final parent is {self.parent}")

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new_value):
        if hasattr(self, 'slider_knob'):  # Only update knob if it exists
            self._value = max(0, min(255, new_value))
            self.slider_knob.rect.x = self.min_x + (self._value * (self.max_x - self.min_x) // 255)
            self.slider_knob.dirty = 2
            if hasattr(self, 'text_sprite'):
                self.text_sprite.text = str(self._value)

    def update_slider_appearance(self):
        """Update the slider's gradient appearance based on its color."""
        for x in range(self.width):
            intensity = int((x / self.width) * 255)
            if self.name == 'R':
                color = (intensity, 0, 0)
            elif self.name == 'G':
                color = (0, intensity, 0)
            elif self.name == 'B':
                color = (0, 0, intensity)
            else:
                color = (intensity, intensity, intensity)
            pygame.draw.line(self.image, color, (x, 0), (x, self.height))

    def update_color_well(self):
        """Update the color well with current value."""
        if hasattr(self.parent, 'color_well'):
            if self.name == 'R':
                self.parent.red_slider.value = self._value
            elif self.name == 'G':
                self.parent.green_slider.value = self._value
            elif self.name == 'B':
                self.parent.blue_slider.value = self._value

            self.parent.color_well.active_color = (
                self.parent.red_slider.value,
                self.parent.green_slider.value,
                self.parent.blue_slider.value,
            )

    def on_left_mouse_button_down_event(self, event):
        mouse = MousePointer(pos=event.pos)
        if pygame.sprite.collide_rect(mouse, self):
            self.log.info(f"Mouse down on slider {self.name}")
            self.dragging = True
            # Update value based on click position
            click_x = max(self.min_x, min(event.pos[0], self.max_x))
            self._value = ((click_x - self.min_x) * 255) // (self.max_x - self.min_x)

            # Create trigger event exactly like right-click does
            trigger = pygame.event.Event(0, {'name': self.name, 'value': self._value})
            if hasattr(self.parent, 'on_slider_event'):
                self.log.info(f"Slider {self.name} calling on_slider_event with value {self._value}")
                self.parent.on_slider_event(event=event, trigger=trigger)
            else:
                self.log.info(f"Parent {self.parent} has no on_slider_event")

            self.value = self._value  # Update display after event

    def on_mouse_motion_event(self, event):
        if self.dragging:
            self.log.info(f"Dragging slider {self.name}")
            # Update value based on drag position
            drag_x = max(self.min_x, min(event.pos[0], self.max_x))
            self._value = ((drag_x - self.min_x) * 255) // (self.max_x - self.min_x)

            # Create trigger event exactly like right-click does
            trigger = pygame.event.Event(0, {'name': self.name, 'value': self._value})
            if hasattr(self.parent, 'on_slider_event'):
                self.log.info(f"Slider {self.name} calling on_slider_event with value {self._value}")
                self.parent.on_slider_event(event=event, trigger=trigger)
            else:
                self.log.info(f"Parent {self.parent} has no on_slider_event")

            self.value = self._value  # Update display after event

    def on_left_mouse_button_up_event(self, event):
        if self.dragging:
            self.log.info(f"Mouse up on slider {self.name}")
            self.dragging = False

    def update(self):
        super().update()
        self.slider_knob.update()
        self.text_sprite.update()

    def update_color_well(self):
        """Update the color well with current value."""
        if hasattr(self.parent, 'color_well'):
            if self.name == 'R':
                self.parent.red_slider.value = self._value
            elif self.name == 'G':
                self.parent.green_slider.value = self._value
            elif self.name == 'B':
                self.parent.blue_slider.value = self._value

            self.parent.color_well.active_color = (
                self.parent.red_slider.value,
                self.parent.green_slider.value,
                self.parent.blue_slider.value,
            )

    def on_left_mouse_button_down_event(self, event):
        mouse = MousePointer(pos=event.pos)
        if pygame.sprite.collide_rect(mouse, self):
            self.log.info(f"Mouse down on slider {self.name}")
            self.dragging = True
            # Update value based on click position
            click_x = max(self.min_x, min(event.pos[0], self.max_x))
            self._value = ((click_x - self.min_x) * 255) // (self.max_x - self.min_x)

            # Create trigger event exactly like right-click does
            trigger = pygame.event.Event(0, {'name': self.name, 'value': self._value})
            if hasattr(self.parent, 'on_slider_event'):
                self.log.info(f"Slider {self.name} calling on_slider_event with value {self._value}")
                self.parent.on_slider_event(event=event, trigger=trigger)
            else:
                self.log.info(f"Parent {self.parent} has no on_slider_event")

            self.value = self._value  # Update display after event

    def on_mouse_motion_event(self, event):
        if self.dragging:
            self.log.info(f"Dragging slider {self.name}")
            # Update value based on drag position
            drag_x = max(self.min_x, min(event.pos[0], self.max_x))
            self._value = ((drag_x - self.min_x) * 255) // (self.max_x - self.min_x)

            # Create trigger event exactly like right-click does
            trigger = pygame.event.Event(0, {'name': self.name, 'value': self._value})
            if hasattr(self.parent, 'on_slider_event'):
                self.log.info(f"Slider {self.name} calling on_slider_event with value {self._value}")
                self.parent.on_slider_event(event=event, trigger=trigger)
            else:
                self.log.info(f"Parent {self.parent} has no on_slider_event")

            self.value = self._value  # Update display after event

    def on_left_mouse_button_up_event(self, event):
        if self.dragging:
            self.log.info(f"Mouse up on slider {self.name}")
            self.dragging = False

    def update(self):
        super().update()
        self.slider_knob.update()
        self.text_sprite.update()

class ColorWellSprite(BitmappySprite):
    """A color well sprite class."""

    log = LOG

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str,
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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
            x=x, y=y, width=width, height=height, name=name, parent=parent, groups=groups
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
            groups=groups,
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

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str | None = None,
        dialog_text: str = 'Would you like to do a thing?',
        confirm_text: str = 'Confirm',
        cancel_text: str = 'Cancel',
        callbacks: Callable | None = None,
        parent: object = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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

        super().__init__(
            x=x, y=y, width=width, height=height, name=name, parent=parent, groups=groups
        )

        # Set border width
        self.border_width = 1

        # Create a black background surface
        self.image = pygame.Surface((width, height))
        self.image.fill((0, 0, 0))

        # Position dialog text at top
        self.dialog_text_sprite = TextBoxSprite(
            name='dialog_text',
            x=x + 20,
            y=y + 20,
            width=width - 40,
            height=20,
            parent=self,
            groups=groups,
        )
        # Set the text after creation
        self.dialog_text_sprite.text_box.text = dialog_text

        # Position input box in middle
        self.input_box = InputBox(
            x=x + 20,
            y=y + (height // 2) - 10,  # Vertically centered
            width=width - 40,
            height=20,
            text='',
            parent=self,
            groups=groups,
        )

        # Position buttons at bottom
        button_y = y + height - 40  # 20px from bottom

        # Cancel on right
        self.cancel_button = ButtonSprite(
            name=cancel_text,
            x=x + width - 95,  # 20px from right edge
            y=button_y,
            width=75,
            height=20,
            parent=self,
            groups=groups
        )

        # Confirm to left of cancel
        self.confirm_button = ButtonSprite(
            name=confirm_text,
            x=x + width - 180,  # 10px gap between buttons
            y=button_y,
            width=75,
            height=20,
            parent=self,
            groups=groups
        )

        self.input_box.activate()

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
        """Update the input dialog."""
        # Clear the surface first
        self.image.fill((0, 0, 0))  # Black background

        # Draw the bounding box
        pygame.draw.rect(
            self.image, (128, 128, 128), Rect(0, 0, self.width, self.height), self.border_width
        )

        # Mark components as dirty
        self.dialog_text_sprite.dirty = 1
        self.cancel_button.dirty = 1
        self.confirm_button.dirty = 1

        # Blit to self.image instead of self.screen
        self.image.blit(
            self.dialog_text_sprite.image,
            (self.dialog_text_sprite.rect.x - self.rect.x, self.dialog_text_sprite.rect.y - self.rect.y),
        )
        self.image.blit(
            self.cancel_button.image,
            (self.cancel_button.rect.x - self.rect.x, self.cancel_button.rect.y - self.rect.y)
        )
        self.image.blit(
            self.confirm_button.image,
            (self.confirm_button.rect.x - self.rect.x, self.confirm_button.rect.y - self.rect.y)
        )
        self.image.blit(
            self.input_box.image,
            (self.input_box.rect.x - self.rect.x, self.input_box.rect.y - self.rect.y)
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
        # Only activate if click was within input box bounds
        if self.input_box.rect.collidepoint(event.pos):
            self.input_box.activate()
        else:
            self.input_box.deactivate()

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
        """Handle key down events."""
        if event.key == pygame.K_TAB:
            self.input_box.activate()
        else:
            self.input_box.on_key_down_event(event)


class MultiLineTextBox(BitmappySprite):
    """A multi-line text box sprite class."""

    log = LOG

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str | None = None,
        text: str = '',
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
        """Initialize a MultiLineTextBox."""
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        self.log.debug(f"Creating MultiLineTextBox: name={name}, pos=({x}, {y}), size=({width}, {height})")

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            parent=parent,
            groups=groups,
            focusable=True
        )

        self._text = text
        self.text = text
        self.active = False
        self.cursor_visible = True
        self.cursor_blink_time = pygame.time.get_ticks()
        self.cursor_blink_rate = 530
        self.cursor_pos = len(text)
        self._last_update_time = pygame.time.get_ticks()
        self._frame_count = 0

        # Initialize selection attributes
        self.selection_start = None
        self.selection_end = None

        # Force continuous updates
        self.dirty = 2

        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.image = self.image.convert_alpha()

        self.font = pygame.font.Font(None, 24)
        self.text_color = WHITE
        self.cursor_color = WHITE

        # Add scroll tracking
        self.scroll_offset = 0
        self.visible_lines = self.height // self.font.get_linesize()

    def update(self) -> None:
        """Update the multi-line text box."""
        self._frame_count += 1
        current_time = pygame.time.get_ticks()
        time_since_last_update = current_time - self._last_update_time
        line_height = self.font.get_linesize()

        self.log.debug(f"\n--- Frame {self._frame_count} ---")
        self.log.debug(f"Update called after {time_since_last_update}ms")
        self.log.debug(f"State: active={self.active}, cursor_visible={self.cursor_visible}")
        self.log.debug(f"Dirty flag: {self.dirty}")

        self._last_update_time = current_time

        # Clear background
        self.image.fill((32, 32, 32, 200))

        # Draw border
        if self.active:
            pygame.draw.rect(self.image, (64, 64, 255), (0, 0, self.width, self.height), 1)
        else:
            pygame.draw.rect(self.image, WHITE, (0, 0, self.width, self.height), 1)

        # Render text with line breaks and scrolling
        if self._text:
            lines = self._text.split('\n')
            total_lines = len(lines)

            # Adjust scroll if needed to keep cursor visible
            cursor_line = self._text[:self.cursor_pos].count('\n')
            if cursor_line - self.scroll_offset >= self.visible_lines:
                self.scroll_offset = cursor_line - self.visible_lines + 1
            elif cursor_line < self.scroll_offset:
                self.scroll_offset = cursor_line

            # Render visible lines
            visible_range = slice(self.scroll_offset, self.scroll_offset + self.visible_lines)
            visible_lines = lines[visible_range]

            y_offset = 5
            for line in visible_lines:
                if line:  # Only render non-empty lines
                    text_surface = self.font.render(line, True, self.text_color)
                    self.image.blit(text_surface, (5, y_offset))
                y_offset += line_height

        # Handle cursor blinking
        if self.active:
            time_since_blink = current_time - self.cursor_blink_time
            if time_since_blink >= self.cursor_blink_rate:
                self.cursor_visible = not self.cursor_visible
                self.cursor_blink_time = current_time

            if self.cursor_visible:
                # Count newlines before cursor to determine y position
                lines_before_cursor = self._text[:self.cursor_pos].count('\n')
                # Only draw cursor if it's in the visible range
                if self.scroll_offset <= lines_before_cursor < self.scroll_offset + self.visible_lines:
                    # Get text width of current line up to cursor
                    current_line_start = self._text[:self.cursor_pos].rindex('\n') + 1 if '\n' in self._text[:self.cursor_pos] else 0
                    current_line_text = self._text[current_line_start:self.cursor_pos]
                    text_width = self.font.size(current_line_text)[0]

                    cursor_x = text_width + 5
                    cursor_y = 5 + ((lines_before_cursor - self.scroll_offset) * line_height)

                    pygame.draw.line(
                        self.image,
                        self.cursor_color,
                        (cursor_x, cursor_y),
                        (cursor_x, cursor_y + 20),
                        2
                    )

        # Force continuous updates
        self.dirty = 2

    def on_left_mouse_button_down_event(self, event: pygame.event.Event) -> None:
        """Handle left mouse button down events."""
        self.log.debug(f"\n--- Mouse Event ---")
        self.log.debug(f"Mouse down at {event.pos}")
        self.log.debug(f"Current rect: {self.rect}")
        self.log.debug(f"Current state: active={self.active}, cursor_visible={self.cursor_visible}")

        if self.rect.collidepoint(event.pos):
            self.active = True
            self.cursor_visible = True
            self.cursor_blink_time = pygame.time.get_ticks()
            pygame.key.start_text_input()
            # Enable key repeat for backspace
            pygame.key.set_repeat(500, 50)  # 500ms delay, 50ms interval

            # Calculate cursor position
            x_rel = event.pos[0] - self.rect.x - 5
            text_width = 0
            for i, char in enumerate(self._text):
                char_width = self.font.size(char)[0]
                if text_width + (char_width / 2) > x_rel:
                    self.cursor_pos = i
                    break
                text_width += char_width
            else:
                self.cursor_pos = len(self._text)

            self.log.debug(f"Activated: cursor_pos={self.cursor_pos}")
            self.log.debug(f"Text input started")
            self.dirty = 2
        else:
            self.active = False
            pygame.key.stop_text_input()
            # Disable key repeat when inactive
            pygame.key.set_repeat()  # Calling with no args disables repeat
            self.log.debug("Deactivated, text input stopped")

    def on_key_down_event(self, event: pygame.event.Event) -> None:
        """Handle key down events."""
        if not self.active:
            return

        mods = pygame.key.get_mods()
        is_paste = (event.key == pygame.K_v and
                    ((mods & pygame.KMOD_CTRL) or (mods & pygame.KMOD_META)))
        is_copy = (event.key == pygame.K_c and
                   ((mods & pygame.KMOD_CTRL) or (mods & pygame.KMOD_META)))
        is_shift = bool(mods & pygame.KMOD_SHIFT)
        is_ctrl = bool(mods & pygame.KMOD_CTRL) or bool(mods & pygame.KMOD_META)

        # Handle Ctrl+Enter for submission
        if event.key == pygame.K_RETURN and is_ctrl:
            if self.parent and hasattr(self.parent, 'on_text_submit_event'):
                self.parent.on_text_submit_event(self._text)
                # Deactivate the text box after submission
                self.active = False
                pygame.key.stop_text_input()
                pygame.key.set_repeat()  # Disable key repeat
                self.log.debug("Deactivated after submission")
            return

        # Handle selection with shift+arrow keys
        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            if is_shift:
                if self.selection_start is None:
                    self.selection_start = self.cursor_pos

                if event.key == pygame.K_LEFT:
                    self.cursor_pos = max(0, self.cursor_pos - 1)
                else:
                    self.cursor_pos = min(len(self._text), self.cursor_pos + 1)
                self.selection_end = self.cursor_pos
                return
            else:
                self.selection_start = None
                self.selection_end = None

        # Handle copy/paste
        if is_copy and self._text:
            try:
                import pyperclip
                if self.selection_start is not None and self.selection_end is not None:
                    start = min(self.selection_start, self.selection_end)
                    end = max(self.selection_start, self.selection_end)
                    selected_text = self._text[start:end]
                    pyperclip.copy(selected_text)
                else:
                    pyperclip.copy(self._text)
            except Exception as e:
                self.log.error(f"Error copying text: {e}")
            return
        elif is_paste:
            try:
                import pyperclip
                clipboard_text = pyperclip.paste()
                if clipboard_text:
                    before_cursor = self._text[:self.cursor_pos]
                    after_cursor = self._text[self.cursor_pos:]
                    self._text = before_cursor + clipboard_text + after_cursor
                    self.cursor_pos += len(clipboard_text)
                    self.text = self._text
            except Exception as e:
                self.log.error(f"Error pasting text: {e}")
            return

        # Handle regular key events
        if event.key == pygame.K_RETURN:
            # Handle newline
            before_cursor = self._text[:self.cursor_pos]
            after_cursor = self._text[self.cursor_pos:]
            self._text = before_cursor + '\n' + after_cursor
            self.cursor_pos += 1
            self.text = self._text
        elif event.key == pygame.K_BACKSPACE:
            if self.cursor_pos > 0:
                self._text = self._text[:self.cursor_pos-1] + self._text[self.cursor_pos:]
                self.cursor_pos -= 1
                self.text = self._text
        elif event.key == pygame.K_DELETE:
            if self.cursor_pos < len(self._text):
                self._text = self._text[:self.cursor_pos] + self._text[self.cursor_pos+1:]
                self.text = self._text
        elif event.key == pygame.K_LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
        elif event.key == pygame.K_RIGHT:
            self.cursor_pos = min(len(self._text), self.cursor_pos + 1)
        elif event.unicode and event.unicode >= ' ':
            before_cursor = self._text[:self.cursor_pos]
            after_cursor = self._text[self.cursor_pos:]
            self._text = before_cursor + event.unicode + after_cursor
            self.cursor_pos += 1
            self.text = self._text

        self.cursor_visible = True
        self.cursor_blink_time = pygame.time.get_ticks()
        self.dirty = 1
        else:
            self.input_box.on_key_down_event(event)

