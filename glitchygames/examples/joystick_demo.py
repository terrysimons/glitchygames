#!/usr/bin/env python3
"""Joystick Demo."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

import pygame.freetype
import pygame.gfxdraw
import pygame.locals
from glitchygames.color import BLACK, BLUE, GREEN, PURPLE, YELLOW
from glitchygames.engine import GameEngine
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
        self.use_gfxdraw = True

        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        self.screen.convert()
        self.screen.fill(BLACK)
        self.image = self.screen
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
                self.screen, self.screen_width // 2, self.screen_height // 2, YELLOW
            )

            self.point = (self.screen_width // 2, self.screen_height // 2)
        else:
            self.point = pygame.draw.line(
                self.screen,
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
                self.screen,
                self.screen_width // 2,
                self.screen_height // 2,
                self.screen_height // 2,
                BLUE,
            )
        else:
            pygame.draw.circle(
                self.screen,
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
            pygame.gfxdraw.polygon(self.screen, pointlist, GREEN)

            # You could also use:
            # pygame.gfxdraw.trigon(self.screen, x1, y1, x2, y2, x3, y3, GREEN)

            self.triangle = pointlist
        else:
            self.triangle = pygame.draw.polygon(self.screen, GREEN, pointlist, 1)

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
            pygame.gfxdraw.rectangle(self.screen, self.rectangle, PURPLE)
        else:
            self.rectangle = pygame.draw.rect(self.screen, PURPLE, self.rectangle, 1)


# TODO: Refactor this into ui.py and/or remove it
# class TextSprite(Sprite):
#     def __init__(self: Self, background_color=BLACKLUCENT, alpha=0, x=0, y=0):
#         self.background_color = background_color
#         self.alpha = alpha
#         self.x = x
#         self.y = y
#         self.text_box = None
#         super().__init__()

#         # Quick and dirty, for now.
#         self.image = pygame.Surface((200, 200))
#         self.screen = pygame.display.get_surface()

#         if not alpha:
#             self.image.set_colorkey(self.background_color)
#             self.image.convert()
#         else:
#             # Enabling set_alpha() and also setting a color
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

#         self.rect = self.image.get_rect()
#         self.rect.x += x
#         self.rect.y += y
#         self.font_manager = FontManager()
#         self.joystick_manager = JoystickManager()
#         self.joystick_count = len(self.joystick_manager.joysticks)

#         # Interiting from object is default in Python 3.
#         # Linters complain if you do it.
#         class TextBox:
#             def __init__(self: Self, font_controller, x, y, line_height=15):
#                 super().__init__()
#                 self.image = None
#                 self.rect = None
#                 self.start_x = x
#                 self.start_y = y
#                 self.x = self.start_x
#                 self.y = self.start_y
#                 self.line_height = line_height

#                 pygame.freetype.set_default_resolution(font_controller.font_dpi)
#                 self.font = pygame.freetype.SysFont(name=font_controller.font,
#                                                     size=font_controller.font_size)

#             def print(self: Self, surface, string):
#                 (self.image, self.rect) = self.font.render(string, WHITE)
#                 surface.blit(self.image, (self.x, self.y))
#                 self.rect.x = self.x
#                 self.rect.y = self.y
#                 self.y += self.line_height

#             def reset(self):
#                 self.x = self.start_x
#                 self.y = self.start_y

#             def indent(self):
#                 self.x += 10

#             def unindent(self):
#                 self.x -= 10

#         self.text_box = TextBox(font_controller=self.font_manager, x=10, y=10)

#         self.dirty = 2

#     def update(self):
#         self.image.fill(self.background_color)

#         pygame.draw.rect(self.image, WHITE, self.image.get_rect(), 7)

#         self.text_box.reset()
#         self.text_box.print(self.image, f'{Game.NAME} version {Game.VERSION}')

#         self.text_box.print(self.image, f'CPUs: {multiprocessing.cpu_count()}')

#         self.text_box.print(self.image, f'FPS: {Game.FPS:.0f}')

#         self.text_box.print(self.image, f'Number of joysticks: {self.joystick_count}')
#         if self.joystick_count:
#             for i, joystick in enumerate(self.joystick_manager.joysticks):
#                 self.text_box.print(self.image, f'Joystick {i}')

#                 # Get the name from the OS for the controller/joystick
#                 self.text_box.indent()
#                 self.text_box.print(self.image, f'Joystick name: {joystick.get_name()}')

#                 # Usually axis run in pairs, up/down for one, and left/right for
#                 # the other.
#                 axes = joystick.get_numaxes()
#                 self.text_box.print(self.image, f'Number of axes: {axes}')

#                 self.text_box.indent()
#                 for j in range(axes):
#                        self.text_box.print(
#                            self.image, f'Axis {j} value: {joystick.get_axis(j):>6.3f}'
#                        )
#                 self.text_box.unindent()

#                 buttons = joystick.get_numbuttons()
#                 self.text_box.print(self.image, f'Number of buttons: {joystick.get_numbuttons()}')

#                 self.text_box.indent()
#                 for j in range(buttons):
#                     self.text_box.print(
#                         self.image, f'Button {j:>2} value: {joystick.get_button(i)}'
#                     )
#                 self.text_box.unindent()

#                 # Hat switch. All or nothing for direction, not like joysticks.
#                 # Value comes back in an array.
#                 hats = 0
#                 self.text_box.print(self.image, f'Number of hats: {hats}')

#                 self.text_box.indent()
#                 for j in range(hats):
#                     self.text_box.print(self.image, f'Hat {j} value: {str(joystick.get_hat(j))}')
#                     self.text_box.unindent()
#                 self.text_box.unindent()


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
        self.shapes_sprite = ShapesSprite(x=0, y=0, width=640, height=480)
        # self.text_sprite = TextSprite(background_color=BLACKLUCENT, alpha=0, x=0, y=0)

        # self.all_sprites = pygame.sprite.LayeredDirty(
        #     tuple(self.shapes_sprite)
        # )

        self.all_sprites.clear(self.screen, self.background)
        self.load_resources()

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
                self.tiles.append(self.load_graphic(resource))

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
