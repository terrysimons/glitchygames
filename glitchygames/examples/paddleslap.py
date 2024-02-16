#!/usr/bin/env python3
"""Paddle Slap.

This is a simple game where you try to keep the ball from hitting your side of the screen.
"""
from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals
from glitchygames.color import BLACKLUCENT, WHITE
from glitchygames.engine import GameEngine
from glitchygames.events.joystick import JoystickManager
from glitchygames.fonts import FontManager
from glitchygames.game_objects import BallSprite
from glitchygames.game_objects.paddle import VerticalPaddle
from glitchygames.game_objects.sounds import SFX
from glitchygames.movement import Speed
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite

log = logging.getLogger('game')
log.setLevel(logging.INFO)


class TextSprite(Sprite):
    """A sprite class for displaying text."""

    def __init__(self: Self, background_color: tuple = BLACKLUCENT, alpha: int = 0,
                 x: int = 0, y: int = 0,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize the text sprite.

        Args:
            background_color (tuple): The background color of the text.
            alpha (int): The alpha value of the text.
            x (int): The x position of the text.
            y (int): The y position of the text.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(x, y, 0, 0, groups=groups)
        self.background_color = background_color
        self.alpha = alpha
        self.x = x
        self.y = y

        # Quick and dirty, for now.
        self.image = pygame.Surface((400, 400))
        self.screen = pygame.display.get_surface()

        if not alpha:
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
            self.image.convert_alpha()
            self.image.set_alpha(self.alpha)

        self.rect = self.image.get_rect()
        self.rect.x += x
        self.rect.y += y
        self.font_manager = FontManager()
        self.joystick_manager = JoystickManager()
        self.joystick_count = len(self.joystick_manager.joysticks)

        # Inheriting from object is default in Python 3.
        # Linters complain if you do it.
        class TextBox(Sprite):
            """A sprite class for displaying text."""

            def __init__(self: Self, font_controller: FontManager, pos: tuple,
                         line_height: int = 15, groups: pygame.sprite.LayeredDirty | None = None) -> None:  # noqa: E501
                """Initialize the text sprite.

                Args:
                    font_controller (FontManager): The font controller to use.
                    pos (tuple): The position of the text.
                    line_height (int): The line height of the text.
                    groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

                Returns:
                    None
                """  # noqa: E501
                if groups is None:
                    groups = pygame.sprite.LayeredDirty()

                super().__init__(pos[0], pos[1], 0, 0, groups=groups)
                self.image = None
                self.start_pos = pos
                self.rect = pygame.Rect(pos, (640, 480))
                self.line_height = line_height

                pygame.freetype.set_default_resolution(font_controller.font_dpi)
                self.font = pygame.freetype.SysFont(name=font_controller.font,
                                                    size=font_controller.font_size)

            def print_text(self: Self, surface: pygame.surface.Surface, string: str) -> None:
                """Print text to the screen.

                Args:
                    surface (pygame.surface.Surface): The surface to print to.
                    string (str): The string to print.

                Returns:
                    None
                """
                (self.image, self.rect) = self.font.render(string, WHITE)
                # self.image
                surface.blit(self.image, self.rect.center)
                self.rect.center = surface.get_rect().center
                self.rect.y += self.line_height

            def reset(self: Self) -> None:
                """Reset the text box.

                Args:
                    None

                Returns:
                    None
                """
                self.rect.center = self.start_pos

            def indent(self: Self) -> None:
                self.rect.x += 10

            def unindent(self: Self) -> None:
                self.rect.x -= 10

        self.text_box = TextBox(font_controller=self.font_manager, pos=self.rect.center)
        self.dirty = 2

    def update(self: Self) -> None:
        """Update the text sprite.

        Args:
            None

        Returns:
            None
        """
        self.image.fill(self.background_color)

        self.text_box.reset()
        self.text_box.print_text(self.image, f'{Game.NAME} version {Game.VERSION}')


class Game(Scene):
    """The main game class.  This is where the magic happens."""
    # Set your game name/version here.
    NAME = 'Paddle Slap'
    VERSION = '1.1'

    def __init__(self: Self, options: dict, groups: pygame.sprite.LayeredDirty | None = None) -> None:  # noqa: E501
        """Initialize the Game.

        Args:
            options (dict): The options passed to the game.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(options=options, groups=groups)
        self.fps = 0

        v_center = self.screen_height / 2
        self.player1 = VerticalPaddle(
            'Player 1',
            (20, 80),
            (0, v_center - 40),
            WHITE,
            Speed(y=10, increment=1),
            collision_sound=SFX.SLAP
        )
        self.player2 = VerticalPaddle(
            'Player 2',
            (20, 80),
            (self.screen_width - 20, v_center - 40),
            WHITE,
            Speed(y=10, increment=1),
            collision_sound=SFX.SLAP
        )
        self.balls = [
            BallSprite(collision_sound=SFX.BOUNCE) for _ in range(self.options.get('balls', 1))
        ]

        for ball in self.balls:
            red = random.randint(0, 255)
            green = random.randint(0, 255)
            blue = random.randint(0, 255)
            ball.color = (red, green, blue)

        self.all_sprites = pygame.sprite.LayeredDirty(
            (
                self.player1,
                self.player2,
                *self.balls
            )
        )

        self.all_sprites.clear(self.screen, self.background)

    @classmethod
    def args(cls: Self, parser: argparse.ArgumentParser) -> None:
        """Add arguments to the argument parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            None
        """
        parser.add_argument('-v', '--version',
                            action='store_true',
                            help='print the game version and exit')

        parser.add_argument('-b', '--balls',
                            type=int,
                            help='the number of balls to start with',
                            default=1)

    def setup(self: Self) -> None:
        """Set up the game.

        Args:
            None

        Returns:
            None
        """
        self.fps = 60
        pygame.key.set_repeat(1)

    def dt_tick(self: Self, dt: float) -> None:
        """Update the game.

        Args:
            dt (float): The delta time.

        Returns:
            None
        """
        self.dt = dt
        self.dt_timer += self.dt

        for sprite in self.all_sprites:
            sprite.dt_tick(dt)

    def update(self: Self) -> None:
        """Update the game.

        Args:
            None

        Returns:
            None
        """
        for ball in self.balls:
            if pygame.sprite.collide_rect(self.player1, ball) and ball.speed.x <= 0:
                # ball.rally.hit()
                # if ball.rally.do_rally():
                #     ball.rally.reset()

                self.player1.snd.play()
                ball.speed.x *= -1

            if pygame.sprite.collide_rect(self.player2, ball) and ball.speed.x > 0:
                # ball.rally.hit()
                # if ball.rally.do_rally():
                #     ball.rally.reset()

                self.player2.snd.play()
                ball.speed.x *= -1

        super().update()

    def on_controller_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        if event.button in {pygame.CONTROLLER_BUTTON_DPAD_UP, pygame.CONTROLLER_BUTTON_DPAD_DOWN}:
            player = self.player1 if event.instance_id == 0 else self.player2
            player.stop()

        self.log.info(f'GOT on_controller_button_down_event: {event}')

    def on_controller_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        player = self.player1 if event.instance_id == 0 else self.player2
        if event.button == pygame.CONTROLLER_BUTTON_DPAD_UP:
            player.up()
        if event.button == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
            player.down()

        self.log.info(f'GOT on_controller_button_up_event: {event}')

    def on_controller_axis_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller axis motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        player = self.player1 if event.instance_id == 0 else self.player2
        if event.axis == pygame.CONTROLLER_AXIS_LEFTY:
            if event.value < 0:
                player.up()
            if event.value == 0:
                player.stop()
            if event.value > 0:
                player.down()
            self.log.info(f'GOT on_controller_axis_motion_event: {event}')

    def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Handle ESC/q to quit
        super().on_key_up_event(event)

        unpressed_keys = pygame.key.get_pressed()

        # KEYUP            key, mod
        if unpressed_keys[pygame.K_UP]:
            self.player1.stop()
        if unpressed_keys[pygame.K_DOWN]:
            self.player1.stop()
        if unpressed_keys[pygame.K_w]:
            self.player2.stop()
        if unpressed_keys[pygame.K_s]:
            self.player2.stop()

    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # KEYDOWN            key, mod
        # self.log.info(f'Key Down Event: {event}')
        pressed_keys = pygame.key.get_pressed()

        if pressed_keys[pygame.K_w]:
            self.player1.up()
        if pressed_keys[pygame.K_s]:
            self.player1.down()
        if pressed_keys[pygame.K_UP]:
            self.player2.up()
        if pressed_keys[pygame.K_DOWN]:
            self.player2.down()


def main() -> None:
    """The main function.

    Args:
        None

    Returns:
        None
    """
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
