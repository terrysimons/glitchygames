#!/usr/bin/env python3
"""Joystick Demo."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
import multiprocessing
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

import pygame
import pygame._sdl2.controller

import glitchygames
from glitchygames.color import BLACK, BLUE, GREEN, PURPLE, WHITE, YELLOW
from glitchygames.engine import GameEngine
from glitchygames.events.joystick import JoystickEventManager
from glitchygames.events.controller import ControllerEventManager
from glitchygames.fonts import FontManager
from glitchygames.ui import TabControlSprite
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite
from pygame import Rect

LOG = logging.getLogger("game")
LOG.setLevel(logging.DEBUG)


class ShapesSprite(Sprite):
    """A sprite class for drawing shapes."""

    def __init__(self: Self, *args, **kwargs) -> None:
        """Initialize a ShapesSprite.

        Args:
            *args: Arguments to pass to the parent class.
            **kwargs: Keyword arguments to pass to the parent class.

        Returns:
            Self

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

        Returns:
            None

        """
        self.rect.center = pos
        self.dirty = 1

    def update(self: Self) -> None:
        """Update the sprite.

        Args:
            None

        Returns:
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

        Returns:
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

        Returns:
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

        Returns:
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

        Returns:
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
    def __init__(self: Self, background_color=BLACK, alpha=0, x=0, y=0, groups=None, game=None):
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

        super().__init__(x=x, y=y, width=self.screen_width, height=self.screen_height, groups=groups)

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

    def _draw_text(self):
        """Obsolete text rendering path (removed)."""
        return

    def update(self, filter_controller_index=None, input_mode=None):
        """Update the text display."""
        self.update_textbox(filter_controller_index, input_mode)
        return

    def update_textbox(self, filter_controller_index=None, input_mode=None):
        """Alternative update method using TextBoxSprite

        Args:
            filter_controller_index (int | None): If set, only show info for this controller index
            input_mode (str | None): The input mode ("joystick" or "controller")
        """
        self.image.fill(self.background_color)

        # Lazy initialize the textbox helper on first use
        if self.text_box is None:
            # Minimal inline helper using freetype via FontManager
            class _InlineTextBox:
                def __init__(self, start_x: int, start_y: int, line_height: int = 15):
                    self.start_x = start_x
                    self.start_y = start_y
                    self.x = start_x
                    self.y = start_y
                    self.line_height = line_height

                def print(self, surface, string: str) -> None:
                    font = FontManager.get_font("freetype")
                    rendered = font.render(string, fgcolor=WHITE, size=10)
                    if isinstance(rendered, tuple):
                        rendered = rendered[0]
                    # Debug: check if text would go beyond surface bounds
                    text_width = rendered.get_width()
                    if self.x + text_width > surface.get_width():
                        print(f"DEBUG: Text '{string}' width {text_width} at x={self.x} exceeds surface width {surface.get_width()}")
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

        # Removed border to maximize text space

        self.text_box.reset()
        self.text_box.print(self.image, f'{Game.NAME} version {Game.VERSION}')

        self.text_box.print(self.image, f'CPUs: {multiprocessing.cpu_count()}')

        self.text_box.print(self.image, f'FPS: {Game.FPS:.0f}')

        # Show controller information - either filtered or all
        # Use passed input_mode or default to joystick
        if input_mode is None:
            input_mode = "joystick"

        if filter_controller_index is not None:
            # Show only the selected controller
            self.text_box.print(self.image, f'Showing {input_mode.title()} {filter_controller_index}')
            active = []

            # Use the correct manager based on input mode
            if input_mode == "controller":
                device_manager = self.controller_manager
                devices = device_manager.controllers
            else:
                device_manager = self.joystick_manager
                devices = device_manager.joysticks

            # Find the controller with the matching device ID
            for joystick_id, proxy in devices.items():
                # Check for the correct attribute based on input mode
                if input_mode == "controller":
                    has_device = hasattr(proxy, 'controller') and proxy.controller is not None
                    device_obj = proxy.controller if has_device else None
                else:
                    has_device = hasattr(proxy, 'joystick') and proxy.joystick is not None
                    device_obj = proxy.joystick if has_device else None

                if has_device and device_obj is not None:
                    # For controllers, use the controller ID directly
                    if input_mode == "controller":
                        current_device_id = joystick_id
                    else:
                        # For joysticks, find the current device index
                        current_device_id = None
                        for i in range(pygame.joystick.get_count()):
                            try:
                                current_device = pygame.joystick.Joystick(i)
                                if current_device is device_obj:
                                    current_device_id = i
                                    break
                            except Exception:
                                pass

                    if current_device_id == filter_controller_index:
                        active.append((joystick_id, proxy, device_obj))
                        break
        else:
            # Show all controllers (original working behavior)
            self.text_box.print(self.image, f'Showing all {input_mode.title()}s')
            active = []

            # Use the correct manager based on input mode
            if input_mode == "controller":
                device_manager = self.controller_manager
                devices = device_manager.controllers
            else:
                device_manager = self.joystick_manager
                devices = device_manager.joysticks

            # Add all controllers
            for joystick_id, proxy in devices.items():
                # Check for the correct attribute based on input mode
                if input_mode == "controller":
                    has_device = hasattr(proxy, 'controller') and proxy.controller is not None
                    device_obj = proxy.controller if has_device else None
                else:
                    has_device = hasattr(proxy, 'joystick') and proxy.joystick is not None
                    device_obj = proxy.joystick if has_device else None

                if has_device and device_obj is not None:
                    active.append((joystick_id, proxy, device_obj))

        if active:
            for i, (joystick_id, proxy, joystick) in enumerate(active):
                # Deep debug: names and GUIDs from both proxy and raw pygame joystick
                # Get names based on input mode
                if input_mode == "controller":
                    try:
                        proxy_name = pygame._sdl2.controller.name_forindex(joystick_id)
                    except Exception:
                        proxy_name = "Unknown Controller"
                    joystick_name = None  # Controllers don't have joystick names
                else:
                    proxy_name = proxy.get_name() if hasattr(proxy, "get_name") else None
                    joystick_name = joystick.get_name() if hasattr(joystick, "get_name") else None
                # Get GUID based on input mode
                if input_mode == "controller":
                    joystick_guid = None  # Controllers don't have GUIDs in the same way
                else:
                    joystick_guid = (
                        "-".join(joystick.get_guid()[i:i+4].upper() for i in range(0, len(joystick.get_guid()), 4))
                        if hasattr(joystick, "get_guid") and joystick.get_guid() else None
                    )
                # For controllers, use joystick_id directly; for joysticks, try to get _device_id
                if input_mode == "controller":
                    device_id = joystick_id
                else:
                    device_id = proxy._device_id if hasattr(proxy, '_device_id') else joystick_id
                instance_id = joystick.get_instance_id() if \
                    hasattr(joystick, "get_instance_id") \
                        else None

                device_type = input_mode.title()
                self.text_box.print(self.image, f'{device_type} {device_id} (id={joystick_id})')

                # Get the name from the OS for the controller/joystick
                self.text_box.indent()
                # Display the proxy name explicitly; this is expected to be specific (e.g., "Xbox 360 Controller")
                self.text_box.print(self.image, f'{device_type} name: {proxy_name}')

                # Display the GUID/UUID
                if joystick_guid:
                    self.text_box.print(self.image, f'{device_type} GUID: {joystick_guid}')
                elif input_mode == "controller":
                    self.text_box.print(self.image, f'{device_type} GUID: N/A (Controller mode)')

                # Display ID and instance ID
                try:
                    device_id = joystick.get_id()
                    self.text_box.print(self.image, f'Device ID: {device_id}')
                except Exception:
                    pass

                try:
                    instance_id = joystick.get_instance_id()
                    self.text_box.print(self.image, f'Instance ID: {instance_id}')
                except Exception:
                    pass

                # Handle axes and buttons based on input mode
                if input_mode == "controller":
                    # Controllers have a different API
                    axes = len(proxy.AXIS) if hasattr(proxy, 'AXIS') else 0
                    self.text_box.print(self.image, f'Number of axes: {axes}')

                    self.text_box.indent()
                    for j in range(axes):
                        try:
                            axis_value = joystick.get_axis(j)
                            self.text_box.print(
                                self.image, f'Axis {j} value: {axis_value:>6.3f}'
                            )
                        except Exception:
                            self.text_box.print(
                                self.image, f'Axis {j} value: N/A'
                            )
                    self.text_box.unindent()

                    buttons = len(proxy.BUTTONS) if hasattr(proxy, 'BUTTONS') else 0
                    self.text_box.print(self.image, f'Number of buttons: {buttons}')

                    self.text_box.indent()
                    for j in range(buttons):
                        try:
                            button_value = joystick.get_button(j)
                            self.text_box.print(
                                self.image, f'Button {j:>2} value: {button_value}'
                            )
                        except Exception:
                            self.text_box.print(
                                self.image, f'Button {j:>2} value: N/A'
                            )
                    self.text_box.unindent()

                    # Controllers don't have hats
                    hats = 0
                else:
                    # Joysticks use the normal API
                    axes = joystick.get_numaxes()
                    self.text_box.print(self.image, f'Number of axes: {axes}')

                    self.text_box.indent()
                    for j in range(axes):
                           self.text_box.print(
                                self.image, f'Axis {j} value: {joystick.get_axis(j):>6.3f}'
                            )
                    self.text_box.unindent()

                    buttons = joystick.get_numbuttons()
                    self.text_box.print(self.image, f'Number of buttons: {buttons}')

                    self.text_box.indent()
                    for j in range(buttons):
                        self.text_box.print(
                            self.image, f'Button {j:>2} value: {joystick.get_button(j)}'
                        )
                    self.text_box.unindent()

                    # Hat switch. All or nothing for direction, not like joysticks.
                    # Value comes back in an array.
                    hats = joystick.get_numhats()
                self.text_box.print(self.image, f'Number of hats: {hats}')

                if hats > 0:
                    self.text_box.indent()
                    for j in range(hats):
                        try:
                            self.text_box.print(self.image, f'Hat {j} value: {str(joystick.get_hat(j))}')
                        except Exception:
                            self.text_box.print(self.image, f'Hat {j} value: N/A')
                self.text_box.unindent()
                self.text_box.unindent()


class JoystickScene(Scene):
    """A scene for testing joysticks."""

    def __init__(self: Self, *, options: dict, groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize the JoystickScene.

        Args:
            options (dict | None): The options passed to the game.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(options=options, groups=groups)
        self.tiles = []

        # self.load_resources()
        self.shapes_sprite = ShapesSprite(x=0, y=0, width=640, height=480, groups=groups)
        self.text_sprite = TextSprite(background_color=BLACK, alpha=0, x=0, y=0, groups=None, game=self)

        # Add the sprites to the all_sprites group (text on top)
        self.all_sprites.add(self.text_sprite)
        self.all_sprites.add(self.shapes_sprite)

        self.all_sprites.clear(self.screen, self.background)
        self.load_resources()

        # Controller tabs state
        self.tab_control = None
        self.active_controller_index = None
        # Use the correct count method based on input mode
        input_mode = self.options.get("input_mode", "joystick")
        if input_mode == "controller":
            self.last_controller_count = pygame._sdl2.controller.get_count()
        else:
            self.last_controller_count = pygame.joystick.get_count()
        self._rebuild_controller_tabs()

    def update(self):
        """Update the scene."""
        super().update()  # Call parent update

        # Fallback: check for controller count changes if events aren't firing
        # Use the correct count method based on input mode
        input_mode = self.options.get("input_mode", "joystick")
        if input_mode == "controller":
            current_count = pygame._sdl2.controller.get_count()
        else:
            current_count = pygame.joystick.get_count()

        if current_count != self.last_controller_count:
            self.last_controller_count = current_count
            self._rebuild_controller_tabs()

        # Manually update the text sprite to refresh button states
        self.text_sprite.update(filter_controller_index=self.active_controller_index, input_mode=self.options.get("input_mode", "joystick"))

        # Keep tabs centered if window size changes dynamically
        if self.tab_control is not None:
            if len(self.tab_control.tabs) > 0:
                total_width = self.tab_control.tab_width * len(self.tab_control.tabs)
                new_x = (self.screen.get_width() - total_width) // 2
                if new_x != self.tab_control.rect.x:
                    self.tab_control.rect.x = new_x
                    self.tab_control.dirty = 2

    def load_resources(self: Self) -> None:
        """Load the resources.

        Args:
            None

        Returns:
            None

        """
        # Load tiles.
        for resource in Path("resources").glob("*"):
            with contextlib.suppress(IsADirectoryError):
                self.log.info(f"Load Resource: {resource}")
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
        if resource.suffix.lower() not in {".png", ".jpg", ".jpeg", ".bmp", ".gif"}:
            return None
        try:
            return pygame.image.load(str(resource)).convert_alpha()
        except Exception as e:
            self.log.info(f"Skipping resource {resource}: {e}")
            return None

    def render(self: Self, screen: pygame.Surface) -> None:
        """Render the scene.

        Args:
            screen (pygame.Surface): The screen to render to.

        Returns:
            None

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

    def _rebuild_controller_tabs(self: Self) -> None:
        """Create or update the controller index tabs centered at the top."""
        # Get input mode for debug output
        input_mode = self.options.get("input_mode", "Not Found")

        # Use the correct count method based on input mode
        if input_mode == "controller":
            pygame_count = pygame._sdl2.controller.get_count()
        else:
            pygame_count = pygame.joystick.get_count()

        # Get the appropriate manager based on input mode
        device_manager = None
        if input_mode == "controller":
            # Always prefer the game engine's controller manager for hotplug events
            if hasattr(self, 'game') and hasattr(self.game, 'controller_manager'):
                device_manager = self.game.controller_manager
            elif hasattr(self, 'text_sprite') and hasattr(self.text_sprite, 'controller_manager'):
                device_manager = self.text_sprite.controller_manager
        else:  # joystick mode
            if hasattr(self, 'game') and hasattr(self.game, 'joystick_manager'):
                device_manager = self.game.joystick_manager
            elif hasattr(self, 'text_sprite') and hasattr(self.text_sprite, 'joystick_manager'):
                device_manager = self.text_sprite.joystick_manager

        # Force cleanup of stale entries in device_manager
        if device_manager:
            # Use the correct attribute name based on input mode
            devices = device_manager.controllers if input_mode == "controller" else device_manager.joysticks

            # Only do stale cleanup for joysticks, not controllers
            if input_mode == "joystick":
                # Get current pygame joystick instance IDs
                current_instance_ids = set()
                for i in range(pygame.joystick.get_count()):
                    try:
                        joystick = pygame.joystick.Joystick(i)
                        instance_id = joystick.get_instance_id()
                        current_instance_ids.add(instance_id)
                    except Exception:
                        pass

                # Remove any device_manager entries that don't match current pygame joysticks
                stale_ids = []
                for joystick_id, proxy in devices.items():
                    if hasattr(proxy, 'joystick') and proxy.joystick is not None:
                        try:
                            instance_id = proxy.joystick.get_instance_id()
                            if instance_id not in current_instance_ids:
                                print(f"DEBUG: {input_mode.title()} {joystick_id} (instance_id={instance_id}) not in current pygame joysticks, marking as stale")
                                stale_ids.append(joystick_id)
                        except Exception as e:
                            print(f"DEBUG: Marking {input_mode} {joystick_id} as stale for removal: {e}")
                            stale_ids.append(joystick_id)

                # Remove stale entries
                for stale_id in stale_ids:
                    if stale_id in devices:
                        print(f"DEBUG: Removing stale {input_mode} {stale_id}")
                        del devices[stale_id]
            else:
                # For controllers, check if we need to add new controllers
                # Get current pygame controller count
                current_pygame_count = pygame._sdl2.controller.get_count()
                current_manager_count = len(devices)

                # If pygame has more controllers than the manager, add them
                if current_pygame_count > current_manager_count:
                    # Find controllers that are in pygame but not in the manager
                    for controller_id in range(current_pygame_count):
                        if controller_id not in devices:
                            try:
                                if pygame._sdl2.controller.is_controller(controller_id):
                                    controller_proxy = ControllerEventManager.ControllerEventProxy(
                                        controller_id=controller_id, game=device_manager.game
                                    )
                                    devices[controller_id] = controller_proxy
                            except Exception as e:
                                pass

                # Do stale cleanup for controllers that are no longer connected
                # Get current pygame controller count
                current_pygame_count = pygame._sdl2.controller.get_count()

                stale_ids = []
                for controller_id, proxy in devices.items():
                    has_device = hasattr(proxy, 'controller') and proxy.controller is not None

                    if not has_device:
                        stale_ids.append(controller_id)
                    else:
                        # Check if the controller ID is still valid by checking if it's within the current count
                        if controller_id >= current_pygame_count:
                            stale_ids.append(controller_id)
                        else:
                            # Try to verify the controller is still valid by checking if it's still a controller
                            try:
                                if not pygame._sdl2.controller.is_controller(controller_id):
                                    stale_ids.append(controller_id)
                                else:
                                    # Additional validation: try to get the controller name
                                    # This helps catch cases where the controller is marked as valid
                                    # but is actually disconnected (common on some Linux systems)
                                    try:
                                        pygame._sdl2.controller.name_forindex(controller_id)
                                    except Exception:
                                        # If we can't get the name, the controller is likely disconnected
                                        stale_ids.append(controller_id)
                            except Exception as e:
                                stale_ids.append(controller_id)

                # Remove stale entries
                for stale_id in stale_ids:
                    if stale_id in devices:
                        del devices[stale_id]

        # Get unique device IDs from the device manager proxies
        unique_ids = []
        if device_manager:
            # Use the correct attribute name based on input mode
            devices = device_manager.controllers if input_mode == "controller" else device_manager.joysticks
            for joystick_id, proxy in devices.items():
                # Check for the correct attribute based on input mode
                if input_mode == "controller":
                    has_device = hasattr(proxy, 'controller') and proxy.controller is not None
                    device_obj = proxy.controller if has_device else None
                else:
                    has_device = hasattr(proxy, 'joystick') and proxy.joystick is not None
                    device_obj = proxy.joystick if has_device else None

                if has_device and device_obj is not None:
                    # Check if the device is still actually connected
                    try:
                        # Try to access a property to see if the device is still valid
                        if input_mode == "controller":
                            # Controllers use different API - get name from pygame controller
                            try:
                                name = pygame._sdl2.controller.name_forindex(joystick_id)
                            except Exception:
                                name = "Unknown Controller"
                            # For controllers, find the current device index by matching the device object
                            device_id = None
                            for i in range(pygame.controller.get_count()):
                                try:
                                    current_device = pygame.controller.Controller(i)
                                    # Match by object identity to get current device index
                                    if current_device is device_obj:
                                        device_id = i
                                        break
                                except Exception:
                                    pass

                            if device_id is None:
                                # Fallback to joystick_id
                                device_id = joystick_id
                        else:
                            # Joysticks use the normal API
                            name = device_obj.get_name()
                            # Find the current device index by matching the device object
                            device_id = None
                            for i in range(pygame.joystick.get_count()):
                                try:
                                    current_device = pygame.joystick.Joystick(i)
                                    # Match by object identity to get current device index
                                    if current_device is device_obj:
                                        device_id = i
                                        break
                                except Exception:
                                    pass

                            if device_id is None:
                                # Fallback to joystick_id
                                device_id = joystick_id

                        if input_mode == "controller":
                            # Controllers don't have get_guid(), skip it
                            guid = "N/A"
                        else:
                            guid = device_obj.get_guid()

                        # Use device_id instead of joystick_id for tabs
                        if device_id not in unique_ids:
                            unique_ids.append(device_id)
                    except Exception as e:
                        pass

        # Sort IDs for consistent ordering
        unique_ids = sorted(unique_ids)
        count = len(unique_ids)

        # No controllers: remove tab control if present
        if count == 0:
            if self.tab_control is not None:
                try:
                    self.all_sprites.remove(self.tab_control)
                except Exception as e:
                    pass
                finally:
                    self.tab_control = None
                    self.active_controller_index = None
            return

        # Build labels from unique controller IDs
        labels = [str(controller_id) for controller_id in unique_ids]

        # Visual sizing
        per_tab_width = 36
        tab_height = 18
        total_width = per_tab_width * len(labels)
        x = (self.screen.get_width() - total_width) // 2
        y = 2

        if self.tab_control is None:
            self.tab_control = TabControlSprite(
                name="Controller Tabs",
                x=x,
                y=y,
                width=total_width,
                height=tab_height,
                parent=self,
                groups=self.all_sprites,
            )
        else:
            # Remove and recreate the tab control to ensure clean visual update
            if self.tab_control is not None:
                try:
                    self.all_sprites.remove(self.tab_control)
                except Exception as e:
                    pass
                finally:
                    self.tab_control = None

            self.tab_control = TabControlSprite(
                name="Controller Tabs",
                x=x,
                y=y,
                width=total_width,
                height=tab_height,
                parent=self,
                groups=self.all_sprites,
            )

        # Update labels and layout
        self.tab_control.tabs = labels
        if len(labels) > 0:
            self.tab_control.tab_width = max(1, total_width // len(labels))

        # Handle active tab selection when controllers are removed
        if self.active_controller_index is None or self.active_controller_index not in unique_ids:
            # Reset to first tab if no valid selection or selected controller was removed
            self.tab_control.active_tab = 0
            self.active_controller_index = unique_ids[0] if unique_ids else None
        else:
            # Keep current selection if it's still valid - find the tab index for this controller ID
            tab_index = unique_ids.index(self.active_controller_index)
            self.tab_control.active_tab = tab_index

        # Force complete redraw to ensure clean appearance
        self.tab_control.dirty = 2
        self.tab_control.update()

        # Refresh the text display to show the correct controller info
        self.text_sprite.update(filter_controller_index=self.active_controller_index, input_mode=self.options.get("input_mode", "joystick"))

    def on_tab_change_event(self: Self, tab_label: str) -> None:
        """Handle tab selection; filter display to show only selected controller."""
        try:
            # Convert tab label (which is a string representation of controller ID) back to int
            self.active_controller_index = int(tab_label)
        except Exception as e:
            self.active_controller_index = None
        # Force text sprite to refresh with new filter
        self.text_sprite.update(filter_controller_index=self.active_controller_index, input_mode=self.options.get("input_mode", "joystick"))
        # Force tab control redraw
        if self.tab_control is not None:
            self.tab_control.dirty = 2

    # Device hotplug events: rebuild tabs
    def on_joy_device_added_event(self: Self, event: pygame.event.Event) -> None:
        # Update the fallback counter to trigger rebuild
        self.last_controller_count = pygame.joystick.get_count()
        self._rebuild_controller_tabs()

    def on_joy_device_removed_event(self: Self, event: pygame.event.Event) -> None:
        # Update the fallback counter to trigger rebuild
        self.last_controller_count = pygame.joystick.get_count()
        self._rebuild_controller_tabs()

    # Controller device events: rebuild tabs
    def on_controller_device_added_event(self: Self, event: pygame.event.Event) -> None:
        # Update the fallback counter to trigger rebuild
        self.last_controller_count = pygame.joystick.get_count()
        self._rebuild_controller_tabs()

    def on_controller_device_removed_event(self: Self, event: pygame.event.Event) -> None:
        # Update the fallback counter to trigger rebuild
        self.last_controller_count = pygame.joystick.get_count()
        self._rebuild_controller_tabs()

    def on_mouse_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.shapes_sprite.move(event.pos)

    def on_left_mouse_button_up(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.post_game_event("recharge", {"item": "bullet", "rate": 1})

    def on_left_mouse_button_down(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.post_game_event("pew pew", {"bullet": "big boomies"})

    def on_pew_pew_event(self: Self, event: pygame.event.Event) -> None:
        """Handle pew pew events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.info(f"PEW PEW Event: {event}")

    def on_recharge_event(self: Self, event: pygame.event.Event) -> None:
        """Handle recharge events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.info(f"Recharge Event: {event}")

    def on_controller_axis_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller axis motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.info("controller Axis motion event")

    def on_controller_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        pass

    def on_controller_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        pass

    def on_controller_device_remapped_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller device remapped events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        pass

    def on_controller_touchpad_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller touchpad down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        pass

    def on_controller_touchpad_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller touchpad motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        pass

    def on_controller_touchpad_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller touchpad up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        pass

    def on_controller_sensor_update_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller sensor update events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        pass


class Game(Scene):
    """The main game class.  This is where the magic happens."""

    # Set your game name/version here.
    NAME = "Joystick and Font Demo"
    VERSION = "0.0"

    def __init__(self: Self, options: dict) -> None:
        """Initialize the game.

        Args:
            options (dict): The options passed to the game.

        Returns:
            None

        """
        super().__init__(options=options)
        self.time = options.get("time")
        self.input_mode = options.get("input_mode", "controller")  # 'joystick' or 'controller'
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
        if self.input_mode == "joystick":
            self.log.info("Blocking controller events")
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
        elif self.input_mode == "controller":
            self.log.info("Controller mode: Not blocking joystick events to preserve controller hotplug")
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

        Returns:
            None

        """
        parser.add_argument(
            "--time", type=int, help="time in seconds to wait before quitting", default=10
        )
        parser.add_argument(
            "-v", "--version", action="store_true", help="print the game version and exit"
        )


def main() -> None:
    """Run the main function.

    Args:
        None

    Returns:
        None

    """
    GameEngine(game=Game).start()


if __name__ == "__main__":
    main()
