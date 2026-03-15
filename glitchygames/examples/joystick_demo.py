#!/usr/bin/env python3
"""Joystick Demo."""

from __future__ import annotations

import contextlib
import logging
import multiprocessing
from pathlib import Path
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

import pygame
import pygame._sdl2.controller
from pygame import Rect

import glitchygames
from glitchygames.color import BLACK, BLUE, GREEN, PURPLE, WHITE, YELLOW
from glitchygames.engine import GameEngine
from glitchygames.events.controller import ControllerEventManager
from glitchygames.events.joystick import JoystickEventManager
from glitchygames.fonts import FontManager
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite
from glitchygames.ui import TabControlSprite

LOG = logging.getLogger('game')
LOG.setLevel(logging.DEBUG)


class ShapesSprite(Sprite):
    """A sprite class for drawing shapes."""

    def __init__(self: Self, *args: object, **kwargs: object) -> None:
        """Initialize a ShapesSprite.

        Args:
            *args: Arguments to pass to the parent class.
            **kwargs: Keyword arguments to pass to the parent class.

        """
        super().__init__(*args, **kwargs)
        self.use_gfxdraw = False

        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        # Create a proper sprite surface instead of using the screen
        self.image = pygame.Surface((self.screen_width, self.screen_height))
        self.image.convert()
        self.image.fill(BLACK)
        self.rect = self.image.get_rect()

        self.point = None
        self.circle = None
        self.triangle = None

        self._draw_point()
        self._draw_triangle()
        self._draw_circle()
        self._draw_rectangle()

        self.dirty = 1

    def move(self: Self, pos: tuple) -> None:
        """Move the sprite to a new position.

        Args:
            pos (tuple): The new position.

        """
        self.rect.center = pos
        self.dirty = 1

    def update(self: Self) -> None:
        """Update the sprite.

        Args:
            None

        """
        self._draw_point()
        self._draw_circle()
        self._draw_rectangle()
        self._draw_triangle()
        self.dirty = 1

    def _draw_point(self: Self) -> None:
        """Draw a yellow point.

        Args:
            None

        """
        # Draw a yellow point.
        # There's no point API, so we'll fake
        # it with the line API.
        if self.use_gfxdraw:
            pygame.gfxdraw.pixel(
                self.image, self.screen_width // 2, self.screen_height // 2, YELLOW
            )

            self.point = (self.screen_width // 2, self.screen_height // 2)
        else:
            self.point = pygame.draw.line(
                self.image,
                YELLOW,
                (self.screen_width // 2, self.screen_height // 2),
                (self.screen_width // 2, self.screen_height // 2),
            )

    def _draw_circle(self: Self) -> None:
        """Draw a blue circle.

        Args:
            None

        """
        # Draw a blue circle.
        if self.use_gfxdraw:
            pygame.gfxdraw.circle(
                self.image,
                self.screen_width // 2,
                self.screen_height // 2,
                self.screen_height // 2,
                BLUE,
            )
        else:
            pygame.draw.circle(
                self.image,
                BLUE,
                (self.screen_width // 2, self.screen_height // 2),
                self.screen_height // 2,
                1,
            )

    def _draw_triangle(self: Self) -> None:
        """Draw a green triangle.

        Args:
            None

        """
        # Draw a green triangle.
        # polygon(Surface, color, pointlist, width=0) -> Rect
        x1 = self.screen_width // 2
        y1 = 0
        x2 = self.rectangle.bottomleft[0]
        y2 = self.rectangle.bottomleft[1] - 1
        x3 = self.rectangle.bottomright[0]
        y3 = self.rectangle.bottomright[1] - 1

        top_point = (x1, y1)
        left_point = (x2, y2)
        right_point = (x3, y3)
        pointlist = (top_point, left_point, right_point)

        if self.use_gfxdraw:
            pygame.gfxdraw.polygon(self.image, pointlist, GREEN)

            # You could also use:
            # pygame.gfxdraw.trigon(self.image, x1, y1, x2, y2, x3, y3, GREEN)

            self.triangle = pointlist
        else:
            self.triangle = pygame.draw.polygon(self.image, GREEN, pointlist, 1)

    @property
    def rectangle(self: Self) -> pygame.rect.Rect:
        """Get the rectangle.

        Args:
            None

        Returns:
            pygame.rect.Rect: The rectangle.

        """
        rect = Rect(0, 0, self.screen_height, self.screen_height)
        rect.center = (self.screen_width / 2, self.screen_height / 2)

        return rect

    def _draw_rectangle(self: Self) -> None:
        """Draw a purple rectangle.

        Args:
            None

        """
        # Draw a purple rectangle.
        # Note that the pygame documentation has a typo
        # Do not use width=1, use 1 instead.
        if self.use_gfxdraw:
            pygame.gfxdraw.rectangle(self.image, self.rectangle, PURPLE)
        else:
            pygame.draw.rect(self.image, PURPLE, self.rectangle, 1)


# TODO: Refactor this into ui.py and/or remove it
class TextSprite(Sprite):
    """Text display sprite for rendering joystick information on screen."""

    def __init__(
        self: Self,
        background_color: tuple = BLACK,
        alpha: int = 0,
        x: int = 0,
        y: int = 0,
        groups: pygame.sprite.LayeredDirty | None = None,
        game: object = None,
    ) -> None:
        """Initialize the text sprite with position and appearance settings."""
        self.background_color = background_color
        self.alpha = alpha
        self.x = x
        self.y = y
        self.text_box = None
        # Enable alternative textbox mode by default
        self.use_textbox = True

        # Get screen dimensions first
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        super().__init__(
            x=x, y=y, width=self.screen_width, height=self.screen_height, groups=groups
        )

        # Quick and dirty, for now.
        self.image = pygame.Surface((self.screen_width, self.screen_height))

        # Make background transparent
        if not alpha:
            self.image.set_colorkey(self.background_color)
            self.image.convert()
        else:
            self.image.convert_alpha()
            self.image.set_alpha(self.alpha)
        #             # key will let you hide the background
        #             # but things that are blited otherwise will
        #             # be translucent.  This can be an easy
        #             # way to get a translucent image which
        #             # does not have a border, but it causes issues
        #             # with edge-bleed.
        #             #
        #             # What if we blitted the translucent background
        #             # to the screen, then copied it and used the copy
        #             # to write the text on top of when translucency
        #             # is set?  That would allow us to also control
        #             # whether the text is opaque or translucent, and
        #             # it would also allow a different translucency level
        #             # on the text than the window.
        #             self.image.convert_alpha()
        #             self.image.set_alpha(self.alpha)

        self.rect = self.image.get_rect()
        self.rect.x += x
        self.rect.y += y
        # Create a joystick manager for this demo, connected to the scene for events
        self.joystick_manager = JoystickEventManager(game=game)

        # Use the game engine's controller manager instead of creating a new one
        # This ensures we get hotplug events from the engine
        if hasattr(game, 'controller_manager'):
            self.controller_manager = game.controller_manager
        else:
            # Fallback: create our own if the game doesn't have one
            self.controller_manager = ControllerEventManager(game=game)
        self.joystick_count = len(self.joystick_manager.joysticks)

        # Track previous button states to detect changes
        self._previous_button_states = {}
        for joystick_id, joystick in self.joystick_manager.joysticks.items():
            if hasattr(joystick, '_buttons'):
                self._previous_button_states[joystick_id] = joystick._buttons.copy()

        # Initial render using the textbox implementation
        self.update_textbox()

    def _draw_text(self: Self) -> None:
        """Obsolete text rendering path (removed)."""
        return

    def update(
        self: Self, filter_controller_index: int | None = None, input_mode: str | None = None
    ) -> None:
        """Update the text display."""
        self.update_textbox(filter_controller_index, input_mode)

    def _get_device_object_from_proxy(
        self: Self, proxy: object, input_mode: str
    ) -> object | None:
        """Extract the device object from a proxy based on input mode.

        Args:
            proxy: The device proxy object.
            input_mode: Either "controller" or "joystick".

        Returns:
            The underlying device object, or None if not available.

        """
        if input_mode == 'controller':
            has_device = hasattr(proxy, 'controller') and proxy.controller is not None
            return proxy.controller if has_device else None

        has_device = hasattr(proxy, 'joystick') and proxy.joystick is not None
        return proxy.joystick if has_device else None

    def _get_devices_for_mode(self: Self, input_mode: str) -> dict:
        """Get the devices dict for the given input mode.

        Args:
            input_mode: Either "controller" or "joystick".

        Returns:
            The devices dictionary from the appropriate manager.

        """
        if input_mode == 'controller':
            return self.controller_manager.controllers
        return self.joystick_manager.joysticks

    def _find_joystick_device_id(
        self: Self, device_obj: object
    ) -> int | None:
        """Find the current pygame device index for a joystick by object identity.

        Args:
            device_obj: The joystick device object to find.

        Returns:
            The device index, or None if not found.

        """
        for i in range(pygame.joystick.get_count()):
            try:
                current_device = pygame.joystick.Joystick(i)
                if current_device is device_obj:
                    return i
            except pygame.error:
                LOG.debug('Failed to access joystick %d during device lookup', i)
        return None

    def _collect_active_devices(
        self: Self, input_mode: str, filter_controller_index: int | None = None
    ) -> list[tuple]:
        """Collect active device tuples (joystick_id, proxy, device_obj).

        Args:
            input_mode: Either "controller" or "joystick".
            filter_controller_index: If set, only return the matching device.

        Returns:
            List of (joystick_id, proxy, device_obj) tuples.

        """
        devices = self._get_devices_for_mode(input_mode)
        active = []

        for joystick_id, proxy in devices.items():
            device_obj = self._get_device_object_from_proxy(proxy, input_mode)
            if device_obj is None:
                continue

            if filter_controller_index is not None:
                # Find the matching device by ID
                if input_mode == 'controller':
                    current_device_id = joystick_id
                else:
                    current_device_id = self._find_joystick_device_id(device_obj)

                if current_device_id == filter_controller_index:
                    active.append((joystick_id, proxy, device_obj))
                    break
            else:
                active.append((joystick_id, proxy, device_obj))

        return active

    def _get_device_display_info(
        self: Self, joystick_id: int, proxy: object, device_obj: object, input_mode: str
    ) -> tuple[str | None, str | None, int]:
        """Get display name, GUID, and device ID for a device.

        Args:
            joystick_id: The joystick/controller ID.
            proxy: The device proxy object.
            device_obj: The underlying device object.
            input_mode: Either "controller" or "joystick".

        Returns:
            Tuple of (proxy_name, guid, device_id).

        """
        if input_mode == 'controller':
            try:
                proxy_name = pygame._sdl2.controller.name_forindex(joystick_id)
            except pygame.error:
                proxy_name = 'Unknown Controller'
            joystick_guid = None
            device_id = joystick_id
        else:
            proxy_name = proxy.get_name() if hasattr(proxy, 'get_name') else None
            joystick_guid = (
                '-'.join(
                    device_obj.get_guid()[i : i + 4].upper()
                    for i in range(0, len(device_obj.get_guid()), 4)
                )
                if hasattr(device_obj, 'get_guid') and device_obj.get_guid()
                else None
            )
            device_id = proxy._device_id if hasattr(proxy, '_device_id') else joystick_id

        return proxy_name, joystick_guid, device_id

    def _render_device_axes_and_buttons(
        self: Self, proxy: object, device_obj: object, input_mode: str
    ) -> None:
        """Render axis, button, and hat information for a device.

        Args:
            proxy: The device proxy object.
            device_obj: The underlying device object.
            input_mode: Either "controller" or "joystick".

        """
        if input_mode == 'controller':
            self._render_controller_inputs(proxy, device_obj)
        else:
            self._render_joystick_inputs(device_obj)

    def _render_controller_inputs(
        self: Self, proxy: object, device_obj: object
    ) -> None:
        """Render controller-specific input info (axes, buttons).

        Args:
            proxy: The controller proxy object.
            device_obj: The underlying controller object.

        """
        axes = len(proxy.AXIS) if hasattr(proxy, 'AXIS') else 0
        self.text_box.print(self.image, f'Number of axes: {axes}')

        self.text_box.indent()
        for j in range(axes):
            try:
                axis_value = device_obj.get_axis(j)
                self.text_box.print(self.image, f'Axis {j} value: {axis_value:>6.3f}')
            except pygame.error:
                self.text_box.print(self.image, f'Axis {j} value: N/A')
        self.text_box.unindent()

        buttons = len(proxy.BUTTONS) if hasattr(proxy, 'BUTTONS') else 0
        self.text_box.print(self.image, f'Number of buttons: {buttons}')

        self.text_box.indent()
        for j in range(buttons):
            try:
                button_value = device_obj.get_button(j)
                self.text_box.print(self.image, f'Button {j:>2} value: {button_value}')
            except pygame.error:
                self.text_box.print(self.image, f'Button {j:>2} value: N/A')
        self.text_box.unindent()

        # Controllers don't have hats
        self.text_box.print(self.image, 'Number of hats: 0')

    def _render_joystick_inputs(self: Self, device_obj: object) -> None:
        """Render joystick-specific input info (axes, buttons, hats).

        Args:
            device_obj: The underlying joystick object.

        """
        axes = device_obj.get_numaxes()
        self.text_box.print(self.image, f'Number of axes: {axes}')

        self.text_box.indent()
        for j in range(axes):
            self.text_box.print(
                self.image, f'Axis {j} value: {device_obj.get_axis(j):>6.3f}'
            )
        self.text_box.unindent()

        buttons = device_obj.get_numbuttons()
        self.text_box.print(self.image, f'Number of buttons: {buttons}')

        self.text_box.indent()
        for j in range(buttons):
            self.text_box.print(
                self.image, f'Button {j:>2} value: {device_obj.get_button(j)}'
            )
        self.text_box.unindent()

        # Hat switch. All or nothing for direction, not like joysticks.
        # Value comes back in an array.
        hats = device_obj.get_numhats()
        self.text_box.print(self.image, f'Number of hats: {hats}')

        if hats > 0:
            self.text_box.indent()
            for j in range(hats):
                try:
                    self.text_box.print(
                        self.image, f'Hat {j} value: {device_obj.get_hat(j)!s}'
                    )
                except pygame.error:
                    self.text_box.print(self.image, f'Hat {j} value: N/A')
            self.text_box.unindent()

    def _render_device_info(
        self: Self, joystick_id: int, proxy: object, device_obj: object, input_mode: str
    ) -> None:
        """Render all information for a single device.

        Args:
            joystick_id: The joystick/controller ID.
            proxy: The device proxy object.
            device_obj: The underlying device object.
            input_mode: Either "controller" or "joystick".

        """
        proxy_name, joystick_guid, device_id = self._get_device_display_info(
            joystick_id, proxy, device_obj, input_mode
        )
        device_type = input_mode.title()

        self.text_box.print(self.image, f'{device_type} {device_id} (id={joystick_id})')
        self.text_box.indent()

        # Display the proxy name
        self.text_box.print(self.image, f'{device_type} name: {proxy_name}')

        # Display the GUID/UUID
        if joystick_guid:
            self.text_box.print(self.image, f'{device_type} GUID: {joystick_guid}')
        elif input_mode == 'controller':
            self.text_box.print(self.image, f'{device_type} GUID: N/A (Controller mode)')

        # Display ID and instance ID
        try:
            raw_device_id = device_obj.get_id()
            self.text_box.print(self.image, f'Device ID: {raw_device_id}')
        except pygame.error:
            LOG.debug('Failed to get device ID for joystick %d', joystick_id)

        try:
            instance_id = device_obj.get_instance_id()
            self.text_box.print(self.image, f'Instance ID: {instance_id}')
        except pygame.error:
            LOG.debug('Failed to get instance ID for joystick %d', joystick_id)

        # Render axes, buttons, and hats
        self._render_device_axes_and_buttons(proxy, device_obj, input_mode)

        self.text_box.unindent()

    def update_textbox(
        self: Self, filter_controller_index: int | None = None, input_mode: str | None = None
    ) -> None:
        """Update the display using TextBoxSprite.

        Args:
            filter_controller_index (int | None): If set, only show info for this controller index
            input_mode (str | None): The input mode ("joystick" or "controller")

        """
        self.image.fill(self.background_color)

        # Lazy initialize the textbox helper on first use
        if self.text_box is None:
            # Minimal inline helper using freetype via FontManager
            class _InlineTextBox:
                def __init__(self, start_x: int, start_y: int, line_height: int = 15) -> None:
                    self.start_x = start_x
                    self.start_y = start_y
                    self.x = start_x
                    self.y = start_y
                    self.line_height = line_height

                def print(self, surface: pygame.Surface, string: str) -> None:
                    font = FontManager.get_font('freetype')
                    rendered = font.render(string, fgcolor=WHITE, size=10)
                    if isinstance(rendered, tuple):
                        rendered = rendered[0]
                    # Debug: check if text would go beyond surface bounds
                    text_width = rendered.get_width()
                    if self.x + text_width > surface.get_width():
                        LOG.debug(
                            f"Text '{string}' width {text_width} "
                            f"at x={self.x} exceeds surface "
                            f"width {surface.get_width()}"
                        )
                    surface.blit(rendered, (self.x, self.y))
                    self.y += self.line_height

                def reset(self) -> None:
                    self.x = self.start_x
                    self.y = self.start_y

                def indent(self) -> None:
                    self.x += 10

                def unindent(self) -> None:
                    self.x -= 10

            self.text_box = _InlineTextBox(start_x=0, start_y=0, line_height=12)

        self.text_box.reset()
        self.text_box.print(self.image, f'{Game.NAME} version {Game.VERSION}')
        self.text_box.print(self.image, f'CPUs: {multiprocessing.cpu_count()}')
        self.text_box.print(self.image, f'FPS: {Game.FPS:.0f}')

        # Use passed input_mode or default to joystick
        if input_mode is None:
            input_mode = 'joystick'

        if filter_controller_index is not None:
            self.text_box.print(
                self.image, f'Showing {input_mode.title()} {filter_controller_index}'
            )
        else:
            self.text_box.print(self.image, f'Showing all {input_mode.title()}s')

        active = self._collect_active_devices(input_mode, filter_controller_index)

        for joystick_id, proxy, device_obj in active:
            self._render_device_info(joystick_id, proxy, device_obj, input_mode)


class JoystickScene(Scene):
    """A scene for testing joysticks."""

    def __init__(
        self: Self, *, options: dict, groups: pygame.sprite.LayeredDirty | None = None
    ) -> None:
        """Initialize the JoystickScene.

        Args:
            options (dict | None): The options passed to the game.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(options=options, groups=groups)
        self.tiles = []

        # self.load_resources()
        self.shapes_sprite = ShapesSprite(x=0, y=0, width=640, height=480, groups=groups)
        self.text_sprite = TextSprite(
            background_color=BLACK, alpha=0, x=0, y=0, groups=None, game=self
        )

        # Add the sprites to the all_sprites group (text on top)
        self.all_sprites.add(self.text_sprite)
        self.all_sprites.add(self.shapes_sprite)

        self.all_sprites.clear(self.screen, self.background)
        self.load_resources()

        # Controller tabs state
        self.tab_control = None
        self.active_controller_index = None
        # Use the correct count method based on input mode
        input_mode = self.options.get('input_mode', 'joystick')
        if input_mode == 'controller':
            self.last_controller_count = pygame._sdl2.controller.get_count()
        else:
            self.last_controller_count = pygame.joystick.get_count()
        self._rebuild_controller_tabs()

    def update(self: Self) -> None:
        """Update the scene."""
        super().update()  # Call parent update

        # Fallback: check for controller count changes if events aren't firing
        # Use the correct count method based on input mode
        input_mode = self.options.get('input_mode', 'joystick')
        if input_mode == 'controller':
            current_count = pygame._sdl2.controller.get_count()
        else:
            current_count = pygame.joystick.get_count()

        if current_count != self.last_controller_count:
            self.last_controller_count = current_count
            self._rebuild_controller_tabs()

        # Manually update the text sprite to refresh button states
        self.text_sprite.update(
            filter_controller_index=self.active_controller_index,
            input_mode=self.options.get('input_mode', 'joystick'),
        )

        # Keep tabs centered if window size changes dynamically
        if self.tab_control is not None and len(self.tab_control.tabs) > 0:
            total_width = self.tab_control.tab_width * len(self.tab_control.tabs)
            new_x = (self.screen.get_width() - total_width) // 2
            if new_x != self.tab_control.rect.x:
                self.tab_control.rect.x = new_x
                self.tab_control.dirty = 2

    def load_resources(self: Self) -> None:
        """Load the resources.

        Args:
            None

        """
        # Load tiles.
        for resource in Path('resources').glob('*'):
            with contextlib.suppress(IsADirectoryError):
                self.log.info(f'Load Resource: {resource}')
                graphic = self.load_graphic(resource)
                if graphic is not None:
                    self.tiles.append(graphic)

    def load_graphic(self: Self, resource: Path) -> pygame.Surface | None:
        """Load an image file as a pygame Surface, or return None if not an image.

        Args:
            resource (Path): The file path to load.

        Returns:
            pygame.Surface | None: Loaded surface or None on failure.

        """
        # Only attempt to load common image types
        if resource.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.bmp', '.gif'}:
            return None
        try:
            return pygame.image.load(str(resource)).convert_alpha()
        except pygame.error as e:
            self.log.info(f'Skipping resource {resource}: {e}')
            return None

    def render(self: Self, screen: pygame.Surface) -> None:
        """Render the scene.

        Args:
            screen (pygame.Surface): The screen to render to.

        """
        super().render(screen)

        x = 0
        y = 0
        tiles_across = 640 / 32
        # tiles_down = 480 / 32
        for i, graphic in enumerate(self.tiles):
            screen.blit(graphic, (x, y))
            if i % tiles_across == 0:
                x = 0
                y += 32
            else:
                x += 32

    def _get_device_manager(self: Self, input_mode: str) -> object | None:
        """Get the appropriate device manager for the input mode.

        Args:
            input_mode: Either "controller" or "joystick".

        Returns:
            The device manager, or None if not found.

        """
        if input_mode == 'controller':
            if hasattr(self, 'game') and hasattr(self.game, 'controller_manager'):
                return self.game.controller_manager
            if hasattr(self, 'text_sprite') and hasattr(self.text_sprite, 'controller_manager'):
                return self.text_sprite.controller_manager
            return None

        if hasattr(self, 'game') and hasattr(self.game, 'joystick_manager'):
            return self.game.joystick_manager
        if hasattr(self, 'text_sprite') and hasattr(self.text_sprite, 'joystick_manager'):
            return self.text_sprite.joystick_manager
        return None

    def _cleanup_stale_joysticks(self: Self, devices: dict) -> None:
        """Remove stale joystick entries that no longer match current pygame joysticks.

        Args:
            devices: The joystick devices dictionary to clean up.

        """
        # Get current pygame joystick instance IDs
        current_instance_ids = set()
        for i in range(pygame.joystick.get_count()):
            try:
                joystick = pygame.joystick.Joystick(i)
                instance_id = joystick.get_instance_id()
                current_instance_ids.add(instance_id)
            except pygame.error:
                LOG.debug('Failed to access joystick %d during stale cleanup', i)

        # Find entries that don't match current pygame joysticks
        stale_ids = []
        for joystick_id, proxy in devices.items():
            if not (hasattr(proxy, 'joystick') and proxy.joystick is not None):
                continue
            try:
                instance_id = proxy.joystick.get_instance_id()
                if instance_id not in current_instance_ids:
                    LOG.debug(
                        'Joystick %d (instance_id=%d) not in current '
                        'pygame joysticks, marking as stale',
                        joystick_id,
                        instance_id,
                    )
                    stale_ids.append(joystick_id)
            except pygame.error as e:
                LOG.debug(f'Marking joystick {joystick_id} as stale for removal: {e}')
                stale_ids.append(joystick_id)

        for stale_id in stale_ids:
            if stale_id in devices:
                LOG.debug(f'Removing stale joystick {stale_id}')
                del devices[stale_id]

    def _add_new_controllers(self: Self, devices: dict, device_manager: object) -> None:
        """Add newly connected controllers that pygame knows about but the manager doesn't.

        Args:
            devices: The controller devices dictionary.
            device_manager: The controller event manager.

        """
        current_pygame_count = pygame._sdl2.controller.get_count()
        if current_pygame_count <= len(devices):
            return

        for controller_id in range(current_pygame_count):
            if controller_id in devices:
                continue
            try:
                if pygame._sdl2.controller.is_controller(controller_id):
                    controller_proxy = ControllerEventManager.ControllerEventProxy(
                        controller_id=controller_id, game=device_manager.game
                    )
                    devices[controller_id] = controller_proxy
            except pygame.error:
                LOG.debug('Failed to add controller %d during hotplug', controller_id)

    def _is_controller_still_valid(self: Self, controller_id: int) -> bool:
        """Check if a controller is still valid and connected.

        Args:
            controller_id: The controller index to check.

        Returns:
            True if the controller is valid, False otherwise.

        """
        try:
            if not pygame._sdl2.controller.is_controller(controller_id):
                return False
            # Additional validation: try to get the controller name.
            # This helps catch cases where the controller is marked as valid
            # but is actually disconnected (common on some Linux systems).
            pygame._sdl2.controller.name_forindex(controller_id)
            return True
        except pygame.error:
            return False

    def _cleanup_stale_controllers(self: Self, devices: dict) -> None:
        """Remove stale controller entries that are no longer connected.

        Args:
            devices: The controller devices dictionary to clean up.

        """
        current_pygame_count = pygame._sdl2.controller.get_count()

        stale_ids = []
        for controller_id, proxy in devices.items():
            has_device = hasattr(proxy, 'controller') and proxy.controller is not None
            is_stale = (
                not has_device
                or controller_id >= current_pygame_count
                or not self._is_controller_still_valid(controller_id)
            )
            if is_stale:
                stale_ids.append(controller_id)

        for stale_id in stale_ids:
            devices.pop(stale_id, None)

    def _find_controller_device_id(
        self: Self, joystick_id: int, device_obj: object
    ) -> int:
        """Find the current device index for a controller by object identity.

        Args:
            joystick_id: Fallback ID if identity match fails.
            device_obj: The controller device object.

        Returns:
            The device index.

        """
        for i in range(pygame.controller.get_count()):
            try:
                current_device = pygame.controller.Controller(i)
                if current_device is device_obj:
                    return i
            except pygame.error:
                LOG.debug('Failed to access controller %d during device lookup', i)
        return joystick_id

    def _collect_unique_device_ids(
        self: Self, device_manager: object, input_mode: str
    ) -> list[int]:
        """Collect unique, validated device IDs from the device manager.

        Args:
            device_manager: The device manager to query.
            input_mode: Either "controller" or "joystick".

        Returns:
            Sorted list of unique device IDs.

        """
        unique_ids = []
        devices = (
            device_manager.controllers
            if input_mode == 'controller'
            else device_manager.joysticks
        )

        for joystick_id, proxy in devices.items():
            device_obj = self.text_sprite._get_device_object_from_proxy(proxy, input_mode)
            if device_obj is None:
                continue

            device_id = self._get_validated_device_id(joystick_id, device_obj, input_mode)
            if device_id is not None and device_id not in unique_ids:
                unique_ids.append(device_id)

        return sorted(unique_ids)

    def _get_validated_device_id(
        self: Self, joystick_id: int, device_obj: object, input_mode: str
    ) -> int | None:
        """Validate a device and return its current device ID.

        Args:
            joystick_id: The proxy's joystick ID (fallback).
            device_obj: The underlying device object.
            input_mode: Either "controller" or "joystick".

        Returns:
            The device ID, or None if validation failed.

        """
        try:
            if input_mode == 'controller':
                device_id = self._find_controller_device_id(joystick_id, device_obj)
            else:
                # Validate by accessing name, then find device index
                device_obj.get_name()
                found_id = self.text_sprite._find_joystick_device_id(device_obj)
                device_id = found_id if found_id is not None else joystick_id

            # Validate the device is reachable (controllers skip GUID check)
            if input_mode != 'controller':
                device_obj.get_guid()

            return device_id
        except pygame.error:
            LOG.debug('Failed to validate device %d, skipping', joystick_id)
            return None

    def _remove_tab_control(self: Self) -> None:
        """Remove the tab control sprite and reset selection state."""
        if self.tab_control is not None:
            try:
                self.all_sprites.remove(self.tab_control)
            except ValueError:
                LOG.debug('Tab control was not in sprite group during removal')
            finally:
                self.tab_control = None
                self.active_controller_index = None

    def _create_tab_control(self: Self, total_width: int, tab_height: int, x: int, y: int) -> None:
        """Create a new TabControlSprite, removing the old one if present.

        Args:
            total_width: Total width of all tabs combined.
            tab_height: Height of each tab.
            x: X position for the tab control.
            y: Y position for the tab control.

        """
        if self.tab_control is not None:
            try:
                self.all_sprites.remove(self.tab_control)
            except ValueError:
                LOG.debug('Tab control was not in sprite group during recreation')
            finally:
                self.tab_control = None

        self.tab_control = TabControlSprite(
            name='Controller Tabs',
            x=x,
            y=y,
            width=total_width,
            height=tab_height,
            parent=self,
            groups=self.all_sprites,
        )

    def _rebuild_controller_tabs(self: Self) -> None:
        """Create or update the controller index tabs centered at the top."""
        input_mode = self.options.get('input_mode', 'Not Found')
        device_manager = self._get_device_manager(input_mode)

        # Force cleanup of stale entries in device_manager
        if device_manager:
            devices = (
                device_manager.controllers
                if input_mode == 'controller'
                else device_manager.joysticks
            )

            if input_mode == 'joystick':
                self._cleanup_stale_joysticks(devices)
            else:
                self._add_new_controllers(devices, device_manager)
                self._cleanup_stale_controllers(devices)

        # Get unique device IDs from the device manager proxies
        if device_manager:
            unique_ids = self._collect_unique_device_ids(device_manager, input_mode)
        else:
            unique_ids = []

        # No controllers: remove tab control if present
        if len(unique_ids) == 0:
            self._remove_tab_control()
            return

        # Build labels from unique controller IDs
        labels = [str(controller_id) for controller_id in unique_ids]

        # Visual sizing
        per_tab_width = 36
        tab_height = 18
        total_width = per_tab_width * len(labels)
        x = (self.screen.get_width() - total_width) // 2
        y = 2

        self._create_tab_control(total_width, tab_height, x, y)

        # Update labels and layout
        self.tab_control.tabs = labels
        if len(labels) > 0:
            self.tab_control.tab_width = max(1, total_width // len(labels))

        # Handle active tab selection when controllers are removed
        if self.active_controller_index is None or self.active_controller_index not in unique_ids:
            self.tab_control.active_tab = 0
            self.active_controller_index = unique_ids[0] if unique_ids else None
        else:
            tab_index = unique_ids.index(self.active_controller_index)
            self.tab_control.active_tab = tab_index

        # Force complete redraw to ensure clean appearance
        self.tab_control.dirty = 2
        self.tab_control.update()

        # Refresh the text display to show the correct controller info
        self.text_sprite.update(
            filter_controller_index=self.active_controller_index,
            input_mode=self.options.get('input_mode', 'joystick'),
        )

    def on_tab_change_event(self: Self, tab_label: str) -> None:
        """Handle tab selection; filter display to show only selected controller."""
        try:
            # Convert tab label (which is a string representation of controller ID) back to int
            self.active_controller_index = int(tab_label)
        except (ValueError, TypeError):
            self.active_controller_index = None
        # Force text sprite to refresh with new filter
        self.text_sprite.update(
            filter_controller_index=self.active_controller_index,
            input_mode=self.options.get('input_mode', 'joystick'),
        )
        # Force tab control redraw
        if self.tab_control is not None:
            self.tab_control.dirty = 2

    # Device hotplug events: rebuild tabs
    def on_joy_device_added_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick device added events by rebuilding controller tabs."""
        # Update the fallback counter to trigger rebuild
        self.last_controller_count = pygame.joystick.get_count()
        self._rebuild_controller_tabs()

    def on_joy_device_removed_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick device removed events by rebuilding controller tabs."""
        # Update the fallback counter to trigger rebuild
        self.last_controller_count = pygame.joystick.get_count()
        self._rebuild_controller_tabs()

    # Controller device events: rebuild tabs
    def on_controller_device_added_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller device added events by rebuilding controller tabs."""
        # Update the fallback counter to trigger rebuild
        self.last_controller_count = pygame.joystick.get_count()
        self._rebuild_controller_tabs()

    def on_controller_device_removed_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller device removed events by rebuilding controller tabs."""
        # Update the fallback counter to trigger rebuild
        self.last_controller_count = pygame.joystick.get_count()
        self._rebuild_controller_tabs()

    def on_mouse_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.shapes_sprite.move(event.pos)

    def on_left_mouse_button_up(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.post_game_event('recharge', {'item': 'bullet', 'rate': 1})

    def on_left_mouse_button_down(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.post_game_event('pew pew', {'bullet': 'big boomies'})

    def on_pew_pew_event(self: Self, event: pygame.event.Event) -> None:
        """Handle pew pew events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.info(f'PEW PEW Event: {event}')

    def on_recharge_event(self: Self, event: pygame.event.Event) -> None:
        """Handle recharge events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.info(f'Recharge Event: {event}')

    def on_controller_axis_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller axis motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.info('controller Axis motion event')

    def on_controller_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """

    def on_controller_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """

    def on_controller_device_remapped_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller device remapped events.

        Args:
            event (pygame.event.Event): The event to handle.

        """

    def on_controller_touchpad_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller touchpad down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """

    def on_controller_touchpad_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller touchpad motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        """

    def on_controller_touchpad_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller touchpad up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """

    def on_controller_sensor_update_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller sensor update events.

        Args:
            event (pygame.event.Event): The event to handle.

        """


class Game(Scene):
    """The main game class.  This is where the magic happens."""

    # Set your game name/version here.
    NAME = 'Joystick and Font Demo'
    VERSION = '0.0'

    def __init__(self: Self, options: dict) -> None:
        """Initialize the game.

        Args:
            options (dict): The options passed to the game.

        """
        super().__init__(options=options)
        self.time = options.get('time')
        self.input_mode = options.get('input_mode', 'controller')  # 'joystick' or 'controller'
        self.next_scene = JoystickScene(options=options)

        # TODO: Write an FPS layer that uses time.ns_time()
        # https://www.pygame.org/docs/ref/display.html#pygame.display.set_mode
        #
        # (0, 0), 0, 0 is the recommended setting for auto-configure.
        # if self.windowed:
        #     self.mode_flags = 0
        # else:
        #     self.mode_flags = pygame.FULLSCREEN
        #     self.screen_width = 0
        #     self.screen_height = 0
        # self.color_depth = 0

        # Uncomment to easily block a class of events, if you
        # don't want them to be processed by the event queue.
        #
        # pygame.event.set_blocked(self.mouse_events)
        # pygame.event.set_blocked(self.joystick_events)
        # pygame.event.set_blocked(self.keyboard_events)

        # Configure input mode: block the opposite family of events
        if self.input_mode == 'joystick':
            self.log.info('Blocking controller events')
            pygame.event.set_blocked(glitchygames.events.CONTROLLER_EVENTS)

            # Note: The above is the same as the following:
            # However, it handles future events automatically.
            #
            # This demo calls it out as a tip for porting pygame code to glitchygames.
            #
            # pygame.event.set_blocked([
            #     pygame.CONTROLLERAXISMOTION,
            #     pygame.CONTROLLERBUTTONDOWN,
            #     pygame.CONTROLLERBUTTONUP,
            #     pygame.CONTROLLERDEVICEADDED,
            #     pygame.CONTROLLERDEVICEREMAPPED,
            #     pygame.CONTROLLERDEVICEREMOVED,
            #     pygame.CONTROLLERTOUCHPADDOWN,
            #     pygame.CONTROLLERTOUCHPADMOTION,
            #     pygame.CONTROLLERTOUCHPADUP,
            # ])
        elif self.input_mode == 'controller':
            self.log.info(
                'Controller mode: Not blocking joystick events to preserve controller hotplug'
            )
            # Note: We don't block joystick events in controller mode because
            # pygame.event.set_blocked(glitchygames.events.JOYSTICK_EVENTS) interferes
            # with CONTROLLERDEVICEADDED/CONTROLLERDEVICEREMOVED event generation on macOS
            # pygame.event.set_blocked(glitchygames.events.JOYSTICK_EVENTS)

            # Same note as above.
            #
            # pygame.event.set_blocked([
            #     pygame.JOYAXISMOTION,
            #     pygame.JOYBUTTONDOWN,
            #     pygame.JOYBUTTONUP,
            #     pygame.JOYDEVICEADDED,
            #     pygame.JOYDEVICEREMOVED,
            #     pygame.JOYHATMOTION,
            #     pygame.JOYBALLMOTION,
            # ])

        # Let's hook up the 'pew pew' event.
        # self.register_game_event('pew pew', self.on_pew_pew_event)

        # And the recharge event.
        # self.register_game_event('recharge', self.on_recharge_event)

    # def update_cursor(self):
    # For giggles, we can draw two cursors.
    # This can cause extra flicker on the cursor.
    #
    # We need to re-configure the various cursor attributes once we do this.
    #    self.cursor = [cursor_row for cursor_row in self.cursor]
    #    self.cursor_width = len(self.cursor[0])
    #    self.cursor_height = len(self.cursor)

    # log.info(f'Custom cursor width: {self.cursor_width}, height: {self.cursor_height}')

    # Now call the GameEngine update_cursor method to compile and set the cursor.
    # super().update_cursor()

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> None:
        """Add arguments to the argument parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        """
        parser.add_argument(
            '--time', type=int, help='time in seconds to wait before quitting', default=10
        )
        parser.add_argument(
            '-v', '--version', action='store_true', help='print the game version and exit'
        )


def main() -> None:
    """Run the main function."""
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
