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
from glitchygames.color import BLACK, BLUE, GREEN, PURPLE, WHITE, YELLOW
from glitchygames.engine import GameEngine
from glitchygames.events.joystick import JoystickManager
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
        self.joystick_manager = JoystickManager(game=game)

        # Also create a controller manager for controller events
        from glitchygames.events.controller import ControllerManager
        self.controller_manager = ControllerManager(game=game)
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

    def update(self, filter_controller_index=None):
        """Update the text display."""
        self.update_textbox(filter_controller_index)
        return

    def update_textbox(self, filter_controller_index=None):
        """Alternative update method using TextBoxSprite

        Args:
            filter_controller_index (int | None): If set, only show info for this controller index
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

        # Build list of active pygame joystick objects from proxies
        active = [
            (joystick_id, proxy, proxy.joystick)
            for joystick_id, proxy in self.joystick_manager.joysticks.items()
            if hasattr(proxy, 'joystick') and proxy.joystick is not None
        ]

        # Filter to show only selected controller if filter is set
        if filter_controller_index is not None:
            print(f"DEBUG: Filtering for controller {filter_controller_index}")
            # Filter by current device ID, not the stored device ID
            filtered_active = []
            for joystick_id, proxy, joystick in active:
                # Find the current device index for this joystick
                current_device_id = None
                for i in range(pygame.joystick.get_count()):
                    try:
                        current_joystick = pygame.joystick.Joystick(i)
                        if current_joystick is joystick:
                            current_device_id = i
                            break
                    except Exception:
                        pass

                print(f"DEBUG: Joystick {joystick_id} has current_device_id={current_device_id}")
                if current_device_id == filter_controller_index:
                    filtered_active.append((joystick_id, proxy, joystick))
                    print(f"DEBUG: Added joystick {joystick_id} to filtered results")

            if filtered_active:
                active = filtered_active
                self.text_box.print(self.image, f'Showing controller {filter_controller_index} (of {len(self.joystick_manager.joysticks)} total)')
            else:
                self.text_box.print(self.image, f'Controller {filter_controller_index} not found')
        else:
            self.text_box.print(self.image, f'Number of joysticks: {len(active)}')

        if active:
            for i, (joystick_id, proxy, joystick) in enumerate(active):
                # Deep debug: names and GUIDs from both proxy and raw pygame joystick
                proxy_name = proxy.get_name() if hasattr(proxy, "get_name") else None
                joystick_name = joystick.get_name() if hasattr(joystick, "get_name") else None
                joystick_guid = (
                    "-".join(joystick.get_guid()[i:i+4].upper() for i in range(0, len(joystick.get_guid()), 4))
                    if hasattr(joystick, "get_guid") and joystick.get_guid() else None
                )
                device_id = proxy._device_id if hasattr(proxy, '_device_id') else joystick_id
                instance_id = joystick.get_instance_id() if \
                    hasattr(joystick, "get_instance_id") \
                        else None

                self.text_box.print(self.image, f'Joystick {device_id} (id={joystick_id})')

                # Get the name from the OS for the controller/joystick
                self.text_box.indent()
                # Display the proxy name explicitly; this is expected to be specific (e.g., "Xbox 360 Controller")
                self.text_box.print(self.image, f'Joystick name: {proxy_name}')

                # Display the GUID/UUID
                if joystick_guid:
                    self.text_box.print(self.image, f'Joystick GUID: {joystick_guid}')

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

                # Usually axis run in pairs, up/down for one, and left/right for
                # the other.
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

                self.text_box.indent()
                for j in range(hats):
                    self.text_box.print(self.image, f'Hat {j} value: {str(joystick.get_hat(j))}')
                self.text_box.unindent()
                self.text_box.unindent()


class JoystickScene(Scene):
    """A scene for testing joysticks."""

    def __init__(self: Self, groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize the JoystickScene.

        Args:
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(groups=groups)
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
        self.last_controller_count = pygame.joystick.get_count()
        self._rebuild_controller_tabs()

    def update(self):
        """Update the scene."""
        super().update()  # Call parent update

        # Fallback: check for controller count changes if events aren't firing
        current_count = pygame.joystick.get_count()
        if current_count != self.last_controller_count:
            print(f"DEBUG: Controller count changed from {self.last_controller_count} to {current_count}")
            self.last_controller_count = current_count
            self._rebuild_controller_tabs()

        # Manually update the text sprite to refresh button states
        self.text_sprite.update(filter_controller_index=self.active_controller_index)

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
        pygame_count = pygame.joystick.get_count()

        # Get the joystick manager from the engine
        joystick_manager = None
        if hasattr(self, 'game') and hasattr(self.game, 'joystick_manager'):
            joystick_manager = self.game.joystick_manager
            print(f"DEBUG: Using engine's joystick manager")
        elif hasattr(self, 'text_sprite') and hasattr(self.text_sprite, 'joystick_manager'):
            joystick_manager = self.text_sprite.joystick_manager
            print(f"DEBUG: Using text sprite's joystick manager")

        # Force cleanup of stale entries in joystick manager
        if joystick_manager:
            # Get current pygame joystick instance IDs
            current_instance_ids = set()
            for i in range(pygame.joystick.get_count()):
                try:
                    joystick = pygame.joystick.Joystick(i)
                    instance_id = joystick.get_instance_id()
                    current_instance_ids.add(instance_id)
                except Exception:
                    pass

            # Remove any joystick manager entries that don't match current pygame joysticks
            stale_ids = []
            for joystick_id, proxy in joystick_manager.joysticks.items():
                if hasattr(proxy, 'joystick') and proxy.joystick is not None:
                    try:
                        instance_id = proxy.joystick.get_instance_id()
                        if instance_id not in current_instance_ids:
                            print(f"DEBUG: Joystick {joystick_id} (instance_id={instance_id}) not in current pygame joysticks, marking as stale")
                            stale_ids.append(joystick_id)
                    except Exception as e:
                        print(f"DEBUG: Marking joystick {joystick_id} as stale for removal: {e}")
                        stale_ids.append(joystick_id)

            # Remove stale entries
            for stale_id in stale_ids:
                if stale_id in joystick_manager.joysticks:
                    print(f"DEBUG: Removing stale joystick {stale_id}")
                    del joystick_manager.joysticks[stale_id]

        # Get unique controller device IDs from the joystick manager proxies
        unique_ids = []
        if joystick_manager:
            print(f"DEBUG: Joystick manager has {len(joystick_manager.joysticks)} entries after cleanup")
            for joystick_id, proxy in joystick_manager.joysticks.items():
                print(f"DEBUG: Found joystick_id={joystick_id}, proxy={proxy}")
                if hasattr(proxy, 'joystick') and proxy.joystick is not None:
                    # Check if the joystick is still actually connected
                    try:
                        # Try to access a property to see if the joystick is still valid
                        name = proxy.joystick.get_name()
                        # Find the current device index by matching the joystick object
                        device_id = None
                        for i in range(pygame.joystick.get_count()):
                            try:
                                current_joystick = pygame.joystick.Joystick(i)
                                # Match by object identity to get current device index
                                if current_joystick is proxy.joystick:
                                    device_id = i
                                    break
                            except Exception:
                                pass

                        if device_id is None:
                            # Fallback to stored device_id or joystick_id
                            device_id = getattr(proxy, '_device_id', joystick_id)

                        print(f"DEBUG: Found current device_id={device_id} for joystick_id={joystick_id}, name='{name}' (should be actual pygame device index)")

                        guid = proxy.joystick.get_guid()
                        print(f"DEBUG: Proxy has valid joystick '{name}', device_id={device_id}, guid={guid}, adding device ID {device_id}")
                        print(f"DEBUG: Found joystick_id={joystick_id}, device_id={device_id}, guid={guid}, proxy={proxy}")
                        # Use device_id instead of joystick_id for tabs
                        if device_id not in unique_ids:
                            unique_ids.append(device_id)
                        else:
                            print(f"DEBUG: Skipping duplicate device ID {device_id}")
                    except Exception as e:
                        print(f"DEBUG: Joystick {joystick_id} is stale/invalid: {e}")
                else:
                    print(f"DEBUG: Proxy has no valid joystick, skipping ID {joystick_id}")

        # Sort IDs for consistent ordering
        unique_ids = sorted(unique_ids)
        count = len(unique_ids)
        print(f"DEBUG: Rebuilding tabs, pygame count: {pygame_count}, unique IDs: {unique_ids}, count: {count}")

        # No controllers: remove tab control if present
        if count == 0:
            if self.tab_control is not None:
                with contextlib.suppress(Exception):
                    self.all_sprites.remove(self.tab_control)
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
            with contextlib.suppress(Exception):
                self.all_sprites.remove(self.tab_control)
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

        print(f"DEBUG: Tab labels: {labels}")
        print(f"DEBUG: unique_ids used for labels: {unique_ids}")
        print(f"DEBUG: Current active_controller_index: {self.active_controller_index}")

        # Handle active tab selection when controllers are removed
        if self.active_controller_index is None or self.active_controller_index not in unique_ids:
            # Reset to first tab if no valid selection or selected controller was removed
            print(f"DEBUG: Resetting to first tab (active_controller_index={self.active_controller_index}, unique_ids={unique_ids})")
            self.tab_control.active_tab = 0
            self.active_controller_index = unique_ids[0] if unique_ids else None
        else:
            # Keep current selection if it's still valid - find the tab index for this controller ID
            tab_index = unique_ids.index(self.active_controller_index)
            print(f"DEBUG: Keeping current selection: {self.active_controller_index} at tab index {tab_index}")
            self.tab_control.active_tab = tab_index

        print(f"DEBUG: Final tab state - active_tab: {self.tab_control.active_tab}, active_controller_index: {self.active_controller_index}")

        # Force complete redraw to ensure clean appearance
        self.tab_control.dirty = 2
        self.tab_control.update()

        # Refresh the text display to show the correct controller info
        self.text_sprite.update(filter_controller_index=self.active_controller_index)

    def on_tab_change_event(self: Self, tab_label: str) -> None:
        """Handle tab selection; filter display to show only selected controller."""
        print(f"DEBUG: on_tab_change_event called with tab_label: {tab_label}")
        try:
            # Convert tab label (which is a string representation of controller ID) back to int
            self.active_controller_index = int(tab_label)
            print(f"DEBUG: Set active_controller_index to: {self.active_controller_index}")
        except Exception as e:
            print(f"DEBUG: Failed to parse tab_label '{tab_label}': {e}")
            self.active_controller_index = None
        # Force text sprite to refresh with new filter
        self.text_sprite.update(filter_controller_index=self.active_controller_index)
        # Force tab control redraw
        if self.tab_control is not None:
            self.tab_control.dirty = 2

    # Device hotplug events: rebuild tabs
    def on_joy_device_added_event(self: Self, event: pygame.event.Event) -> None:
        print(f"DEBUG: Joystick device added event: {event}")
        # Update the fallback counter to trigger rebuild
        self.last_controller_count = pygame.joystick.get_count()
        print(f"DEBUG: Triggering tab rebuild due to joystick device added")
        self._rebuild_controller_tabs()

    def on_joy_device_removed_event(self: Self, event: pygame.event.Event) -> None:
        print(f"DEBUG: Joystick device removed event: {event}")
        # Update the fallback counter to trigger rebuild
        self.last_controller_count = pygame.joystick.get_count()
        print(f"DEBUG: Triggering tab rebuild due to joystick device removed")
        self._rebuild_controller_tabs()

    # Controller device events: rebuild tabs
    def on_controller_device_added_event(self: Self, event: pygame.event.Event) -> None:
        print(f"DEBUG: Controller device added event: {event}")
        # Update the fallback counter to trigger rebuild
        self.last_controller_count = pygame.joystick.get_count()
        print(f"DEBUG: Triggering tab rebuild due to controller device added")
        self._rebuild_controller_tabs()

    def on_controller_device_removed_event(self: Self, event: pygame.event.Event) -> None:
        print(f"DEBUG: Controller device removed event: {event}")
        # Update the fallback counter to trigger rebuild
        self.last_controller_count = pygame.joystick.get_count()
        print(f"DEBUG: Triggering tab rebuild due to controller device removed")
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
        self.next_scene = JoystickScene()

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
            pygame.event.set_blocked([
                pygame.CONTROLLERAXISMOTION,
                pygame.CONTROLLERBUTTONDOWN,
                pygame.CONTROLLERBUTTONUP,
                pygame.CONTROLLERDEVICEADDED,
                pygame.CONTROLLERDEVICEREMAPPED,
                pygame.CONTROLLERDEVICEREMOVED,
                pygame.CONTROLLERTOUCHPADDOWN,
                pygame.CONTROLLERTOUCHPADMOTION,
                pygame.CONTROLLERTOUCHPADUP,
            ])
        else:
            pygame.event.set_blocked([
                pygame.JOYAXISMOTION,
                pygame.JOYBUTTONDOWN,
                pygame.JOYBUTTONUP,
                pygame.JOYDEVICEADDED,
                pygame.JOYDEVICEREMOVED,
                pygame.JOYHATMOTION,
                pygame.JOYBALLMOTION,
            ])

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
        parser.add_argument(
            "--input-mode",
            choices=["joystick", "controller"],
            default="controller",
            help="Choose input event family to use (default: controller)",
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
