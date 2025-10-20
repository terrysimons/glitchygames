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
        # Create a joystick manager for this demo
        self.joystick_manager = JoystickManager()
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

    def update(self):
        """Update the text display."""
        self.update_textbox()
        return

    def update_textbox(self):
        """Alternative update method using TextBoxSprite"""
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
                    surface.blit(rendered, (self.x, self.y))
                    self.y += self.line_height

                def reset(self) -> None:
                    self.x = self.start_x
                    self.y = self.start_y

                def indent(self) -> None:
                    self.x += 10

                def unindent(self) -> None:
                    self.x -= 10

            self.text_box = _InlineTextBox(start_x=10, start_y=10, line_height=12)

        pygame.draw.rect(self.image, WHITE, self.image.get_rect(), 7)

        self.text_box.reset()
        self.text_box.print(self.image, f'{Game.NAME} version {Game.VERSION}')

        self.text_box.print(self.image, f'CPUs: {multiprocessing.cpu_count()}')

        self.text_box.print(self.image, f'FPS: {Game.FPS:.0f}')

        # Build list of active pygame joystick objects from proxies
        active = [
            (jid, proxy, proxy.joystick)
            for jid, proxy in self.joystick_manager.joysticks.items()
            if hasattr(proxy, 'joystick') and proxy.joystick is not None
        ]
        self.text_box.print(self.image, f'Number of joysticks: {len(active)}')
        if active:
            for i, (jid, proxy, js) in enumerate(active):
                # Deep debug: names and GUIDs from both proxy and raw pygame joystick
                proxy_name = None
                js_name = None
                proxy_guid = getattr(proxy, "_guid", None)
                js_guid = None
                try:
                    proxy_name = proxy.get_name() if hasattr(proxy, "get_name") else None
                except Exception as e:
                    print(f"DEBUG name proxy exception for jid={jid}: {e}")
                try:
                    js_name = js.get_name() if hasattr(js, "get_name") else None
                except Exception as e:
                    print(f"DEBUG name js exception for jid={jid}: {e}")
                try:
                    js_guid = js.get_guid() if hasattr(js, "get_guid") else None
                except Exception as e:
                    print(f"DEBUG guid js exception for jid={jid}: {e}")



                self.text_box.print(self.image, f'Joystick {i} (id={jid}')

                # Get the name from the OS for the controller/joystick
                self.text_box.indent()
                # Display the proxy name explicitly; this is expected to be specific (e.g., "Xbox 360 Controller")
                self.text_box.print(self.image, f'Joystick name: {proxy_name}')

                # Usually axis run in pairs, up/down for one, and left/right for
                # the other.
                axes = js.get_numaxes()
                self.text_box.print(self.image, f'Number of axes: {axes}')

                self.text_box.indent()
                for j in range(axes):
                       self.text_box.print(
                            self.image, f'Axis {j} value: {js.get_axis(j):>6.3f}'
                        )
                self.text_box.unindent()

                buttons = js.get_numbuttons()
                self.text_box.print(self.image, f'Number of buttons: {buttons}')

                self.text_box.indent()
                for j in range(buttons):
                    self.text_box.print(
                        self.image, f'Button {j:>2} value: {js.get_button(j)}'
                    )
                self.text_box.unindent()

                # Hat switch. All or nothing for direction, not like joysticks.
                # Value comes back in an array.
                hats = js.get_numhats()
                self.text_box.print(self.image, f'Number of hats: {hats}')

                self.text_box.indent()
                for j in range(hats):
                    self.text_box.print(self.image, f'Hat {j} value: {str(js.get_hat(j))}')
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

    def update(self):
        """Update the scene."""
        super().update()  # Call parent update

        # Manually update the text sprite to refresh button states
        self.text_sprite.update()

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
