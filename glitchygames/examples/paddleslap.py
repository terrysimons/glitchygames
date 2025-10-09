#!/usr/bin/env python3
"""Paddle Slap.

This is a simple game where you try to keep the ball from hitting your side of the screen.
"""

from __future__ import annotations

import logging
import math
import random
import secrets
import time
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

import pygame
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

log = logging.getLogger("game")
log.setLevel(logging.INFO)


class TextSprite(Sprite):
    """A sprite class for displaying text."""

    def __init__(
        self: Self,
        background_color: tuple = BLACKLUCENT,
        alpha: int = 0,
        x: int = 0,
        y: int = 0,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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

            def __init__(
                self: Self,
                font_controller: FontManager,
                pos: tuple,
                line_height: int = 15,
                groups: pygame.sprite.LayeredDirty | None = None,
            ) -> None:
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
                self.font = pygame.freetype.SysFont(
                    name=font_controller.font, size=font_controller.font_size
                )

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
        self.text_box.print_text(self.image, f"{Game.NAME} version {Game.VERSION}")


class Game(Scene):
    """The main game class.  This is where the magic happens."""

    # Set your game name/version here.
    NAME = "Paddle Slap"
    VERSION = "1.1"

    def __init__(
        self: Self, options: dict, groups: pygame.sprite.LayeredDirty | None = None
    ) -> None:
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
        # FPS will be set by command line arguments or default to 60
        
        # Set random seed for reproducible randomness
        seed = int(time.perf_counter() * 1000000) % 2**32
        random.seed(seed)
        log.info(f"Random seed set to: {seed}")

        v_center = self.screen_height / 2
        self.player1 = VerticalPaddle(
            "Player 1",
            (20, 80),
            (0, v_center - 40),
            WHITE,
            Speed(y=10, increment=1),
            collision_sound=SFX.SLAP,
        )
        self.player2 = VerticalPaddle(
            "Player 2",
            (20, 80),
            (self.screen_width - 20, v_center - 40),
            WHITE,
            Speed(y=10, increment=1),
            collision_sound=SFX.SLAP,
        )
        self.balls = []
        for _ in range(self.options.get("balls", 1)):
            ball = BallSprite(collision_sound=SFX.BOUNCE)
            # Set a more reasonable speed for the ball
            ball.speed = Speed(3.0, 1.5)  # Balanced starting speed
            # Add collision cooldown tracking
            ball.collision_cooldowns = {}
            self.balls.append(ball)

        for ball in self.balls:
            red = secrets.randbelow(256)
            green = secrets.randbelow(256)
            blue = secrets.randbelow(256)
            ball.color = (red, green, blue)

        self.all_sprites = pygame.sprite.LayeredDirty((self.player1, self.player2, *self.balls))

        self.all_sprites.clear(self.screen, self.background)

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> None:
        """Add arguments to the argument parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            None

        """
        parser.add_argument(
            "-v", "--version", action="store_true", help="print the game version and exit"
        )

        parser.add_argument(
            "-b", "--balls", type=int, help="the number of balls to start with", default=1
        )

    def setup(self: Self) -> None:
        """Set up the game.

        Args:
            None

        Returns:
            None

        """
        # Set default FPS to 60 if not specified by command line
        if self.target_fps == 0:
            self.target_fps = 60
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
                self.player1.snd.play()
                print(f"PADDLE 1 HIT: ball speed before={math.sqrt(ball.speed.x**2 + ball.speed.y**2):.2f}")
                ball.speed.x *= -1
                # Tell the ball to speed up
                ball.speed_up(1.15)  # 15% speed increase
                print(f"PADDLE 1 HIT: ball speed after={math.sqrt(ball.speed.x**2 + ball.speed.y**2):.2f}")
                # Spawn a new ball at default speed
                self._spawn_new_ball()

            if pygame.sprite.collide_rect(self.player2, ball) and ball.speed.x > 0:
                self.player2.snd.play()
                print(f"PADDLE 2 HIT: ball speed before={math.sqrt(ball.speed.x**2 + ball.speed.y**2):.2f}")
                ball.speed.x *= -1
                # Tell the ball to speed up
                ball.speed_up(1.15)  # 15% speed increase
                print(f"PADDLE 2 HIT: ball speed after={math.sqrt(ball.speed.x**2 + ball.speed.y**2):.2f}")
                # Spawn a new ball at default speed
                self._spawn_new_ball()

        # Check for ball-to-ball collisions
        self._handle_ball_collisions()
        
        # Remove dead balls from our list
        balls_to_remove = []
        for ball in self.balls:
            if not ball.alive():
                balls_to_remove.append(ball)
        
        for ball in balls_to_remove:
            self.balls.remove(ball)

        super().update()

    def _spawn_new_ball(self: Self) -> None:
        """Spawn a new ball at default speed.

        Args:
            None

        Returns:
            None

        """
        # Create new ball at default speed
        new_ball = BallSprite(collision_sound=SFX.BOUNCE)
        new_ball.speed = Speed(3.0, 1.5)  # Balanced starting speed
        new_ball.color = (secrets.randbelow(256), secrets.randbelow(256), secrets.randbelow(256))
        # Add collision cooldown tracking
        new_ball.collision_cooldowns = {}
        
        # Add to balls list and sprite group
        self.balls.append(new_ball)
        self.all_sprites.add(new_ball)

    def _handle_ball_collisions(self: Self) -> None:
        """Handle ball-to-ball collisions with proper physics.

        Args:
            None

        Returns:
            None

        """
        import math
        
        # Check all pairs of balls for collisions
        for i in range(len(self.balls)):
            for j in range(i + 1, len(self.balls)):
                ball1 = self.balls[i]
                ball2 = self.balls[j]
                
                # Calculate distance between ball centers
                dx = ball2.rect.centerx - ball1.rect.centerx
                dy = ball2.rect.centery - ball1.rect.centery
                distance = math.sqrt(dx*dx + dy*dy)
                
                # Check if balls are colliding (sum of radii)
                collision_distance = ball1.rect.width // 2 + ball2.rect.width // 2
                
                # Calculate overlap percentage
                overlap_percentage = (collision_distance - distance) / collision_distance if collision_distance > 0 else 0
                
                # Require 0% overlap for billiards-style collision (touch to bounce)
                if distance < collision_distance and distance > 0 and overlap_percentage >= 0.0:
                    import time
                    current_time = time.time()
                    
                    # Check if balls are in cooldown period
                    ball1_id = id(ball1)
                    ball2_id = id(ball2)
                    
                    # Check if ball1 has cooldown with ball2
                    if ball1_id in ball1.collision_cooldowns and ball1.collision_cooldowns[ball1_id] > current_time - 2.0:
                        continue
                    
                    # Check if ball2 has cooldown with ball1  
                    if ball2_id in ball2.collision_cooldowns and ball2.collision_cooldowns[ball2_id] > current_time - 2.0:
                        continue
                    
                    # Play collision sound
                    if hasattr(ball1, "snd") and ball1.snd is not None:
                        ball1.snd.play()
                    
                    print(f"BALL-TO-BALL: ball1 speed before={math.sqrt(ball1.speed.x**2 + ball1.speed.y**2):.2f}, ball2 speed before={math.sqrt(ball2.speed.x**2 + ball2.speed.y**2):.2f}")
                    
                    # Simple billiards-style collision
                    # Calculate collision normal
                    nx = dx / distance
                    ny = dy / distance
                    
                    # Calculate relative velocity
                    dvx = ball2.speed.x - ball1.speed.x
                    dvy = ball2.speed.y - ball1.speed.y
                    
                    # Calculate relative velocity along collision normal
                    dvn = dvx * nx + dvy * ny
                    
                    # Do not resolve if velocities are separating
                    if dvn > 0:
                        continue
                    
                    # Proper elastic collision physics for equal mass balls
                    # For equal mass elastic collision, each ball gets the other's velocity
                    # component along the collision normal
                    # This ensures both energy and momentum conservation
                    
                    # Calculate velocity components along collision normal
                    v1n = ball1.speed.x * nx + ball1.speed.y * ny
                    v2n = ball2.speed.x * nx + ball2.speed.y * ny
                    
                    # Exchange velocity components along normal
                    # Each ball gets the other's normal velocity component
                    ball1.speed.x += (v2n - v1n) * nx
                    ball1.speed.y += (v2n - v1n) * ny
                    ball2.speed.x += (v1n - v2n) * nx
                    ball2.speed.y += (v1n - v2n) * ny
                    
                    print(f"BALL-TO-BALL: ball1 speed after={math.sqrt(ball1.speed.x**2 + ball1.speed.y**2):.2f}, ball2 speed after={math.sqrt(ball2.speed.x**2 + ball2.speed.y**2):.2f}")
                    
                    # Separate balls to prevent sticking
                    overlap = collision_distance - distance
                    separation_distance = max(overlap, 2.0)  # Minimum 2px separation
                    
                    separation_x = nx * separation_distance * 0.5
                    separation_y = ny * separation_distance * 0.5
                    
                    ball1.rect.x -= separation_x
                    ball1.rect.y -= separation_y
                    ball2.rect.x += separation_x
                    ball2.rect.y += separation_y
                    
                    # Set cooldown timestamps to prevent immediate re-collision
                    ball1.collision_cooldowns[ball2_id] = current_time
                    ball2.collision_cooldowns[ball1_id] = current_time

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

        self.log.info(f"GOT on_controller_button_down_event: {event}")

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

        self.log.info(f"GOT on_controller_button_up_event: {event}")

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
            self.log.info(f"GOT on_controller_axis_motion_event: {event}")

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
    """Run the main function.

    Args:
        None

    Returns:
        None

    """
    GameEngine(game=Game).start()


if __name__ == "__main__":
    main()
