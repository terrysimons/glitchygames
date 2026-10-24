"""GlitchyGames UI menu components.

This module contains the MenuBar and MenuItem widget classes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames import events
from glitchygames.color import WHITE
from glitchygames.events.mouse import MousePointer
from glitchygames.recording import post_event
from glitchygames.sprites import (
    BitmappySprite,
    FocusableSingletonBitmappySprite,
)

if TYPE_CHECKING:
    from glitchygames.events.base import (
        HashableEvent,
        MouseButtonEvent,
        MouseMotionEvent,
        MouseWheelEvent,
    )

LOG = logging.getLogger('game.ui')
LOG.addHandler(logging.NullHandler())


class MenuBar(FocusableSingletonBitmappySprite):
    """A menu bar class."""

    log = LOG

    def __init__(
        self: Self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        name: str | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize a MenuBar.

        Args:
            x (int | float): The x coordinate of the menu bar.
            y (int | float): The y coordinate of the menu bar.
            width (int | float): The width of the menu bar.
            height (int | float): The height of the menu bar.
            name (str | None): The name of the menu bar.
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups to add the sprite to.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)
        self.all_sprites: pygame.sprite.LayeredDirty[Any] = groups
        self.background_color: tuple[int, ...] = (0, 255, 0)
        self.border_width: int = 2
        self.menu_items: dict[str | None, MenuItem] = {}
        self.menu_offset_x = self.border_width
        self.menu_offset_y = self.border_width
        self.width = width
        self.height = height
        self.has_focus = False
        self.log.debug('MENUBAR GROUPS: %s', groups)

        # Create surface with alpha support
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.image = self.image.convert_alpha()

        # Create RGBA colors
        menu_bg_color = (WHITE[0], WHITE[1], WHITE[2], 128)  # Semi-transparent white
        border_color = (WHITE[0], WHITE[1], WHITE[2], 128)  # Semi-transparent white

        # Draw with alpha
        pygame.draw.rect(self.image, menu_bg_color, self.rect)
        pygame.draw.rect(self.image, border_color, self.rect, self.border_width)

        # Always refresh the menu bar.
        self.dirty = 2

    def add_menu(self: Self, menu: MenuItem) -> None:
        """Add a menu to the menu bar."""
        self.menu_items[menu.name] = menu  # ty: ignore[invalid-assignment]
        self.log.info(
            'Before offset: menu %s at x=%s, offset=%s',
            menu.name,
            menu.rect.x,
            self.menu_offset_x,
        )
        menu.image.set_colorkey((255, 0, 255))
        menu.add(self.groups())

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

        self.log.info('After offset: menu %s at x=%s', menu.name, menu.rect.x)
        self.menu_offset_x = menu.rect.x + menu.rect.width + self.border_width
        self.log.debug('Menu Items: %s', self.menu_items)

    def add_menu_item(self: Self, menu_item: MenuItem, menu: MenuBar | None = None) -> None:
        """Add a menu item to the menu bar.

        Args:
            menu_item (MenuItem): The menu item to add.
            menu (MenuBar | None): The menu to add the menu item to.

        """
        if menu is None:
            self.add_menu(menu=menu_item)
            self.log.debug('%s Adding new menu %s.', type(self), menu_item)
        else:
            self.log.debug('%s Adding menu item %s to menu %s.', type(self), menu_item, menu)

    @override
    def update(self: Self) -> None:
        """Update the menu bar."""
        for menu_item in self.menu_items.values():
            # Blit with alpha support
            self.image.blit(menu_item.image, (menu_item.rect.x, menu_item.rect.y))

        if self.has_focus:
            focus_color = (WHITE[0], WHITE[1], WHITE[2], 128)
            pygame.draw.rect(self.image, focus_color, self.rect, 1)

    @override
    def on_left_mouse_drag_event(
        self: Self, event: MouseMotionEvent, trigger: MouseButtonEvent
    ) -> None:
        """Handle left mouse drag events.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Not logged: a drag arrives with every mouse motion while a button is held, so a log
        # line here would run every frame of a drag and drown out useful debug output.

    @override
    def on_left_mouse_drop_event(
        self: Self,
        event: MouseButtonEvent,
        trigger: MouseButtonEvent | None = None,
    ) -> None:
        """Handle left mouse drop events.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (HashableEvent | None): The object that triggered the event.

        """
        self.log.debug('%s Mouse Drop %s', type(self), self.name)

    @override
    def on_middle_mouse_drag_event(
        self: Self,
        event: MouseMotionEvent,
        trigger: MouseButtonEvent | None = None,
    ) -> None:
        """Handle middle mouse drag events.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (HashableEvent | None): The object that triggered the event.

        """
        # Not logged: a drag arrives with every mouse motion while a button is held, so a log
        # line here would run every frame of a drag and drown out useful debug output.

    @override
    def on_middle_mouse_drop_event(
        self: Self,
        event: MouseButtonEvent,
        trigger: MouseButtonEvent | None = None,
    ) -> None:
        """Handle middle mouse drop events.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (HashableEvent | None): The object that triggered the event.

        """
        self.log.debug('%s Mouse Drop %s', type(self), self.name)

    @override
    def on_mouse_drag_event(self: Self, event: MouseMotionEvent, trigger: MouseButtonEvent) -> None:
        """Handle mouse drag events.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        # Not logged: a drag arrives with every mouse motion while a button is held, so a log
        # line here would run every frame of a drag and drown out useful debug output.

    @override
    def on_mouse_drop_event(self: Self, event: MouseButtonEvent, trigger: MouseButtonEvent) -> None:
        """Handle mouse drop events.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (object): The object that triggered the event.

        """
        self.log.debug('%s Mouse Drop %s', type(self), self.name)

    @override
    def on_mouse_motion_event(self: Self, event: MouseMotionEvent) -> None:
        """Handle mouse motion events.

        Args:
            event (MouseMotionEvent): The event to handle.

        """
        # Not logged: motion arrives every frame while the mouse moves over the menu bar, so a
        # log line here would drown out useful debug output.

    @override
    def on_mouse_enter_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse enter events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug('%s ENTER MENU %s', type(self), self.name)
        # Figure out which item was entered.
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse,
            group=self.all_sprites,
            dokill=False,
        )

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.debug(
                    '%s %s Mouse enter on %s at %s', type(self), self.name, self.name, mouse
                )
                collided_sprite.on_mouse_enter_event(event)

                for menu_item in collided_sprite.menu_items:
                    collided_sprite.menu_items[menu_item].on_mouse_enter_event(event)

        self.has_focus = True

    @override
    def on_mouse_exit_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse exit events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # Figure out which item was entered.
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse,
            group=self.all_sprites,
            dokill=False,
        )

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.debug(
                    '%s %s Mouse exit on %s at %s', type(self), self.name, self.name, mouse
                )
                collided_sprite.on_mouse_exit_event(event)

                for menu_item in collided_sprite.menu_items:
                    collided_sprite.menu_items[menu_item].on_mouse_exit_event(event)

        self.has_focus = False

    @override
    def on_left_mouse_button_down_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle left mouse button down events.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # Figure out which item was clicked.
        mouse = MousePointer(pos=event.pos)

        sprites = pygame.sprite.spritecollide(sprite=mouse, group=self.all_sprites, dokill=False)

        for sprite in sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            # if sprite.name in self.menu_items:
            if isinstance(sprite, MenuItem):
                self.log.debug('%s Mouse button down on %s at %s', type(self), self.name, mouse)
                sprite.on_left_mouse_button_down_event(event)

                for menu_item in sprite.menu_items:
                    sprite.menu_items[menu_item].on_left_mouse_button_down_event(event)

    @override
    def on_left_mouse_button_up_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle left mouse button up events.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        mouse = MousePointer(pos=event.pos)

        sprites = pygame.sprite.spritecollide(sprite=mouse, group=self.all_sprites, dokill=False)

        for sprite in sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            # if sprite.name in self.menu_items:
            if isinstance(sprite, MenuItem):
                self.log.debug(
                    '%s %s Mouse button up on %s at %s',
                    type(self),
                    self.name,
                    self.name,
                    mouse,
                )
                sprite.on_left_mouse_button_down_event(event)

                for menu_item in sprite.menu_items:
                    sprite.menu_items[menu_item].on_left_mouse_button_up_event(event)

    @override
    def on_right_mouse_drag_event(
        self: Self,
        event: MouseMotionEvent,
        trigger: MouseButtonEvent | None = None,
    ) -> None:
        """Handle right mouse drag events.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (HashableEvent | None): The object that triggered the event.

        """
        # Not logged: a drag arrives with every mouse motion while a button is held, so a log
        # line here would run every frame of a drag and drown out useful debug output.

    @override
    def on_right_mouse_drop_event(
        self: Self,
        event: MouseButtonEvent,
        trigger: MouseButtonEvent | None = None,
    ) -> None:
        """Handle right mouse drop events.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (HashableEvent | None): The object that triggered the event.

        """
        self.log.debug('%s Mouse Drop %s', type(self), self.name)

    @override
    def on_mouse_wheel_event(
        self: Self,
        event: MouseWheelEvent,
        trigger: HashableEvent | None = None,
    ) -> None:
        """Handle mouse wheel events.

        Args:
            event (MouseWheelEvent): The event to handle.
            trigger (HashableEvent | None): The object that triggered the event.

        """
        self.log.debug('%s Mouse Wheel %s', type(self), self.name)


class MenuItem(BitmappySprite):
    """A menu item class.

    This class represents a menu item.  It can be a root level menu item or a sub menu item.

    """

    log = LOG

    def __init__(
        self: Self,
        x: float = 0,
        y: float = 0,
        width: float = 1,
        height: float = 1,
        *,
        name: str | None = None,
        filename: str | None = None,
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize a MenuItem.

        Args:
            x (int | float): The x coordinate of the menu item.
            y (int | float): The y coordinate of the menu item.
            width (int | float): The width of the menu item.
            height (int | float): The height of the menu item.
            name (str | None): The name of the menu item.
            filename (str | None): The filename of the menu item.
            parent (object | None): The parent of the menu item.
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups to add the sprite to.

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
        self.all_sprites: pygame.sprite.LayeredDirty[Any] = groups

        self.log.debug('MENUITEM GROUPS: %s', groups)

        self.background_color: tuple[int, ...] = (255, 0, 255)
        self.border_width: int = 2
        self.menu_items: dict[str | None, MenuItem] = {}
        self.menu_offset_x: int = self.border_width
        self.menu_offset_y: int = self.border_width
        self.menu_image: pygame.Surface = pygame.Surface((0, 0))
        self.menu_rect: pygame.FRect | pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.menu_down_image: pygame.Surface = pygame.Surface((0, 0))
        self.menu_down_rect: pygame.FRect | pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.menu_up_image: pygame.Surface = pygame.Surface((0, 0))
        self.menu_up_rect: pygame.FRect | pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.is_active: bool = False
        self.name = name
        self.parent = parent

        # Don't set a name for the icon.
        if self.name:
            # Avoid circular import: TextSprite is in text_widgets.py
            from glitchygames.ui.text_widgets import TextSprite

            self.image.fill((255, 255, 255))
            self.image.set_colorkey((255, 255, 255))
            self.text = TextSprite(
                background_color=(255, 255, 255),  # White background to match menu
                text_color=(0, 0, 0),
                x=x,
                y=y,
                width=self.width,
                height=self.height,
                text=self.name,
                parent=parent,
                groups=groups,
            )
            # Align the rect with the text position
            self.rect.x = self.text.rect.x
            self.rect.y = self.text.rect.y

        self.menu_up_image = self.image
        self.menu_up_rect = self.rect
        self.menu_down_image = self.menu_up_image
        self.menu_down_rect = self.menu_up_rect

    @override
    def add(self: Self, *groups: Any) -> None:
        """Add the sprite to a group.

        Args:
            *groups: The groups to add the sprite to.

        """
        # There's something funky with MRO and pygame
        # doing things this way avoids dirtier tricks.
        try:
            text = getattr(self, 'text')  # ruff: ignore[get-attr-with-constant]
            text.add(*groups)
        except AttributeError:
            pass

    def add_menu(self: Self, menu: MenuItem) -> None:
        """Add a menu to the menu item.

        Args:
            menu (MenuItem): The menu to add.

        """
        menu.image.set_colorkey((255, 0, 255))
        menu.add(self.groups())
        menu.add(self.all_sprites)
        if not len(self.menu_items.keys()):
            self.menu_offset_y += int(self.rect.height)
        else:
            menu.rect.x += self.menu_offset_x
            menu.rect.y += self.menu_offset_y
            self.menu_offset_y += int(menu.rect.height)

        self.menu_items[menu.name] = menu  # ty: ignore[invalid-assignment]

        # Now recreate the menu image for later use.
        self.menu_image = pygame.Surface((400, 300))
        self.menu_image.convert()
        self.menu_image.set_colorkey((255, 0, 255))
        self.menu_image.fill((255, 255, 255))
        self.menu_rect = self.menu_image.get_rect()
        self.menu_rect.x = self.rect.x
        self.menu_rect.y = 21

        # A sub-menu without a rect takes no room; with none, the dropped-down menu keeps this
        # item's own size (max() over no rects raised ValueError: BUGS.md #136)
        menu_rects = [
            self.menu_items[mi].rect
            for mi in self.menu_items
            if self.menu_items[mi].rect is not None  # pyright: ignore[reportUnnecessaryComparison]
        ]
        width = max((r.width + 20) for r in menu_rects) * 2.5 if menu_rects else self.rect.width
        heights = [r.height for r in menu_rects]
        height = self.rect.height

        if heights:
            self.log.debug('Heights: %s', heights)
            heights.append(self.rect.height)
            self.log.debug('New Heights: %s', heights)
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
            if menu_item.rect is None:  # pyright: ignore[reportUnnecessaryComparison]
                continue
            menu_item.rect.y = y_offset
            menu_item.rect.width = menu_item.text.width
            menu_item.rect.height = menu_item.text.height
            self.menu_down_image.blit(menu_item.image, (menu_item.rect.x, menu_item.rect.y))
            y_offset += menu_item.rect.height

    def add_menu_item(self: Self, menu_item: MenuItem, menu: MenuBar | None) -> None:
        """Add a menu item to the menu item.

        Args:
            menu_item (MenuItem): The menu item to add.
            menu (MenuBar): The menu to add the menu item to.

        """
        if menu is None:
            self.add_menu(menu=menu_item)
            self.log.debug('%s Adding new menu %s.', type(self), menu_item)
        else:
            self.log.debug('%s Adding menu item %s to menu %s.', type(self), menu_item, menu)

    @override
    def update(self: Self) -> None:
        """Update the menu item."""
        # Draw to our own surface instead of the screen
        if self.is_active and self.menu_image and self.menu_rect:
            self.log.debug('Drawing the menu')
            self.image.blit(self.menu_image, (0, 0))  # Draw relative to our own surface

    @override
    def on_left_mouse_drag_event(
        self: Self, event: MouseMotionEvent, trigger: MouseButtonEvent
    ) -> None:
        """Handle left mouse drag events.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (object): The trigger object.

        """
        # Not logged: a drag arrives with every mouse motion while a button is held, so a log
        # line here would run every frame of a drag and drown out useful debug output.

    @override
    def on_left_mouse_drop_event(
        self: Self, event: MouseButtonEvent, trigger: MouseButtonEvent
    ) -> None:
        """Handle left mouse drop events.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (object): The trigger object.

        """
        self.log.debug('%s Mouse Drop %s', type(self), self.name)

    @override
    def on_middle_mouse_drag_event(
        self: Self,
        event: MouseMotionEvent,
        trigger: MouseButtonEvent,
    ) -> None:
        """Handle middle mouse drag events.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (object): The trigger object.

        """
        # Not logged: a drag arrives with every mouse motion while a button is held, so a log
        # line here would run every frame of a drag and drown out useful debug output.

    @override
    def on_middle_mouse_drop_event(
        self: Self,
        event: MouseButtonEvent,
        trigger: MouseButtonEvent,
    ) -> None:
        """Handle middle mouse drop events.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (object): The trigger object.

        """
        self.log.debug('%s Mouse Drop %s', type(self), self.name)

    @override
    def on_mouse_drag_event(self: Self, event: MouseMotionEvent, trigger: MouseButtonEvent) -> None:
        """Handle mouse drag events.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (object): The trigger object.

        """
        # Not logged: a drag arrives with every mouse motion while a button is held, so a log
        # line here would run every frame of a drag and drown out useful debug output.

    @override
    def on_mouse_drop_event(self: Self, event: MouseButtonEvent, trigger: MouseButtonEvent) -> None:
        """Handle mouse drop events.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (object): The trigger object.

        """
        self.log.debug('%s Mouse Drop %s', type(self), self.name)

    @override
    def on_mouse_motion_event(self: Self, event: MouseMotionEvent) -> None:
        """Handle mouse motion events.

        Args:
            event (MouseMotionEvent): The event to handle.

        """
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse,
            group=self.all_sprites,
            dokill=False,
        )

        for collided_sprite in collided_sprites:
            if collided_sprite.name in self.menu_items:
                self.log.debug(
                    'Mouse enter on %s %s at %s',
                    collided_sprite.name,
                    collided_sprite.rect,
                    mouse.rect,
                )
                collided_sprite.on_mouse_motion_event(event)

                # menu_items maps names to items: iterate the items (iterating the dict gave
                # the names, strings without handlers)
                for submenu in collided_sprite.menu_items.values():
                    submenu.on_mouse_motion_event(event)

        self.has_focus = False

    @override
    def on_mouse_enter_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse enter events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug('%s ENTER MENU %s', type(self), self.name)
        # Figure out which item was entered.
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse,
            group=self.all_sprites,
            dokill=False,
        )

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.debug(
                    'Mouse enter on %s %s at %s',
                    collided_sprite.name,
                    collided_sprite.rect,
                    mouse.rect,
                )
                collided_sprite.on_mouse_enter_event(event)

                for submenu in collided_sprite.menu_items.values():
                    submenu.on_mouse_enter_event(event)

        self.has_focus = True

    @override
    def on_mouse_exit_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse exit events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # Figure out which item was entered.
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse,
            group=self.all_sprites,
            dokill=False,
        )

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                self.log.debug(
                    'Mouse exit on %s %s at %s',
                    collided_sprite.name,
                    collided_sprite.rect,
                    mouse,
                )
                collided_sprite.on_mouse_exit_event(event)

                # Leaving the item leaves its sub-items too (this sent them an enter event)
                for submenu in collided_sprite.menu_items.values():
                    submenu.on_mouse_exit_event(event)

        self.has_focus = False
        self.dirty = 1

    @override
    def on_left_mouse_button_up_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle left mouse button up events.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        self.log.debug('%s Mouse Up %s', type(self), self.name)
        self.image = self.menu_up_image
        self.rect = self.menu_up_rect
        self.is_active = False
        self.dirty = 2
        self.update()

        # Figure out which item was clicked.
        mouse = MousePointer(pos=event.pos)

        self.log.debug('Process MOUSE UP %s at %s', event, mouse)

        sprites = pygame.sprite.spritecollide(sprite=mouse, group=self.all_sprites, dokill=False)

        for sprite in sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            # if sprite.name in self.menu_items:
            if isinstance(sprite, MenuItem):
                self.log.debug('Mouse button up on %s at %s', sprite.name, mouse.rect)

                self.log.debug(
                    '%s Clicked Menu Item: Name: %s, '
                    'Width: %s,'
                    'Height: %s, '
                    'Clicked X: %s, Clicked Y: %s,'
                    'my X: %s, '
                    'my Y: %s',
                    type(self),
                    sprite.name,
                    sprite.rect.width,
                    sprite.rect.height,
                    mouse.rect.x,
                    mouse.rect.y,
                    sprite.rect.x,
                    sprite.rect.y,
                )
                menu_item_callback = sprite.callbacks.get('on_menu_item_event', None)

                if menu_item_callback:
                    menu_item_callback(self, event)
                # Create a menu item clicked event.
                # Emit it to the pygame event subsystem.
                post_event(
                    pygame.event.Event(events.MENUEVENT, {'menu': self, 'menu_item': sprite}),
                )

    @override
    def on_left_mouse_button_down_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle left mouse button down events.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        self.log.debug('%s Mouse Down %s', type(self), self.name)
        self.image = self.menu_down_image
        self.rect = self.menu_down_rect
        self.is_active = True
        self.dirty = 2

        self.update()

        # Figure out which item was clicked.
        mouse = MousePointer(pos=event.pos)

        collided_sprites = pygame.sprite.spritecollide(
            sprite=mouse,
            group=self.all_sprites,
            dokill=False,
        )

        for collided_sprite in collided_sprites:
            # Click the menu item.
            #
            # Don't click sub menus.
            if collided_sprite.name in self.menu_items:
                clicked_sprite: object = collided_sprite
                self.log.debug(
                    '%s Mouse button down on %s at %s',
                    type(clicked_sprite),
                    collided_sprite.name,
                    mouse.rect,
                )
                collided_sprite.on_left_mouse_button_down_event(event)

    @override
    def on_right_mouse_drag_event(
        self: Self,
        event: MouseMotionEvent,
        trigger: MouseButtonEvent | None = None,
    ) -> None:
        """Handle right mouse drag events.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (HashableEvent | None): The object that triggered the event.

        """
        # Not logged: a drag arrives with every mouse motion while a button is held, so a log
        # line here would run every frame of a drag and drown out useful debug output.

    @override
    def on_right_mouse_drop_event(
        self: Self,
        event: MouseButtonEvent,
        trigger: MouseButtonEvent | None = None,
    ) -> None:
        """Handle right mouse drop events.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (HashableEvent | None): The object that triggered the event.

        """
        self.log.debug('%s Mouse Drop %s', type(self), self.name)

    @override
    def on_mouse_wheel_event(
        self: Self,
        event: MouseWheelEvent,
        trigger: HashableEvent | None = None,
    ) -> None:
        """Handle mouse wheel events.

        Args:
            event (MouseWheelEvent): The event to handle.
            trigger (HashableEvent | None): The object that triggered the event.

        """
        self.log.debug('%s Mouse Wheel %s', type(self), self.name)
