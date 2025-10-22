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
from glitchygames.scenes.builtin_scenes.game_over_scene import GameOverScene
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.fonts import FontManager
from glitchygames.game_objects import BallSprite
from glitchygames.game_objects.ball import SpeedUpMode, BallSpawnMode
from glitchygames.game_objects.paddle import VerticalPaddle
from glitchygames.game_objects.sounds import SFX
from glitchygames.movement import Speed
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite

log = logging.getLogger("game")
log.setLevel(logging.DEBUG)  # Enable debug logging to catch weird ball movement


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
        self._space_pressed = False

        # Set random seed for reproducible randomness
        seed = int(time.perf_counter() * 1000000) % 2**32
        random.seed(seed)
        log.info(f"Random seed set to: {seed}")

        v_center = self.screen_height / 2
        self.player1 = VerticalPaddle(
            "Player 1",
            (20, 100),  # Smaller paddle - 100 pixels tall
            (0, v_center - 50),  # Center vertically
            WHITE,
            400,  # 400 pixels per second
            collision_sound=SFX.SLAP,
        )
        self.player2 = VerticalPaddle(
            "Player 2",
            (20, 100),  # Smaller paddle - 100 pixels tall
            (self.screen_width - 20, v_center - 50),  # Center vertically
            WHITE,
            400,  # 400 pixels per second
            collision_sound=SFX.SLAP,
        )
        self.balls = []
        self.last_ball_spawn_time = 0.0  # Track when we last spawned a ball
        self.ball_spawn_cooldown = 2.0  # Minimum 2 seconds between ball spawns
        # Convert string argument to BallSpawnMode flag
        spawn_mode_str = self.options.get("ball_spawn_mode", "paddle_only")
        if spawn_mode_str == "paddle_only":
            self.ball_spawn_mode = BallSpawnMode.PADDLE_ONLY
        elif spawn_mode_str == "wall_only":
            self.ball_spawn_mode = BallSpawnMode.WALL_ONLY
        elif spawn_mode_str == "ball_only":
            self.ball_spawn_mode = BallSpawnMode.BALL_ONLY
        elif spawn_mode_str == "frequent":
            self.ball_spawn_mode = BallSpawnMode.FREQUENT_SPAWNING
        elif spawn_mode_str == "rare":
            self.ball_spawn_mode = BallSpawnMode.PADDLE_ONLY | BallSpawnMode.RARE
        elif spawn_mode_str == "none":
            self.ball_spawn_mode = BallSpawnMode.NO_SPAWNING
        else:
            self.ball_spawn_mode = BallSpawnMode.PADDLE_ONLY
        for _ in range(self.options.get("balls", 1)):
            ball = BallSprite(
                collision_sound=SFX.BOUNCE,
                bounce_top_bottom=True,   # Bounce off top and bottom walls
                bounce_left_right=False,  # Don't bounce off side walls (scoring)
                speed_up_mode=SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X,  # Logarithmic speed up on X only for paddle hits
                speed_up_multiplier=1.15,  # 15% speed increase
                speed_up_interval=1.0  # Not used for paddle-only mode
            )
            # Set a more reasonable speed for the ball (pixels per second)
            ball.speed = Speed(250.0, 125.0)  # 250 pixels/second horizontal, 125 pixels/second vertical
            # Add collision cooldown tracking
            ball.collision_cooldowns = {}
            # Set up paddle collision callback for ball spawn (with speed limit check)
            ball.on_paddle_collision = self._spawn_new_ball_with_speed_check
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

        parser.add_argument(
            "--ball-spawn-mode", type=str,
            help="ball spawn mode (paddle_only, wall_only, ball_only, frequent, rare, none)",
            default="paddle_only",
            choices=["paddle_only", "wall_only", "ball_only", "frequent", "rare", "none"]
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

        # Debug log ball positions and speeds before update
        for i, ball in enumerate(self.balls):
            if ball.alive():
                # Track trajectory over time to detect curving
                if not hasattr(ball, '_debug_positions'):
                    ball._debug_positions = []

                ball._debug_positions.append((ball.rect.x, ball.rect.y, ball.speed.x, ball.speed.y))

                # Keep only last 10 positions for trajectory analysis
                if len(ball._debug_positions) > 10:
                    ball._debug_positions.pop(0)

                # Check for upward curving pattern
                if len(ball._debug_positions) >= 5:
                    positions = ball._debug_positions
                    # Calculate if ball is curving upward
                    y_positions = [pos[1] for pos in positions]
                    if len(set(y_positions)) > 1:  # Only if Y is changing
                        y_trend = y_positions[-1] - y_positions[0]
                        if y_trend < -5:  # Moving upward significantly
                            log.debug(
                                f"BALL {i+1} UPWARD CURVE DETECTED: "
                                f"y_trend={y_trend:.1f} positions={y_positions[-3:]} "
                                f"speed=({ball.speed.x:.1f},{ball.speed.y:.1f})"
                            )

                log.debug(
                    f"BALL {i+1} BEFORE: pos=({ball.rect.x:.1f},{ball.rect.y:.1f}) "
                    f"speed=({ball.speed.x:.1f},{ball.speed.y:.1f}) "
                    f"magnitude={math.sqrt(ball.speed.x**2 + ball.speed.y**2):.1f}"
                )

        for sprite in self.all_sprites:
            sprite.dt_tick(dt)

        # Debug log ball positions and speeds after update
        for i, ball in enumerate(self.balls):
            if ball.alive():
                log.debug(
                    f"BALL {i+1} AFTER:  pos=({ball.rect.x:.1f},{ball.rect.y:.1f}) "
                    f"speed=({ball.speed.x:.1f},{ball.speed.y:.1f}) "
                    f"magnitude={math.sqrt(ball.speed.x**2 + ball.speed.y**2):.1f}"
                )

    def update(self: Self) -> None:
        """Update the game.

        Args:
            None

        Returns:
            None

        """
        for i, ball in enumerate(self.balls):
            if not ball.alive():
                continue

            # Debug log ball state before collision checks
            log.debug(
                f"BALL {i+1} COLLISION CHECK: pos=({ball.rect.x:.1f},{ball.rect.y:.1f}) "
                f"speed=({ball.speed.x:.1f},{ball.speed.y:.1f}) "
                f"paddle1_rect=({self.player1.rect.x},{self.player1.rect.y},{self.player1.rect.width},{self.player1.rect.height}) "
                f"paddle2_rect=({self.player2.rect.x},{self.player2.rect.y},{self.player2.rect.width},{self.player2.rect.height})"
            )

            # Paddle collision handling is now done in BallSprite._check_paddle_collisions()
            # The new system prevents clipping and triggers ball spawn via callback

        # Check for ball-to-ball collisions
        self._handle_ball_collisions()

        # Remove dead balls from our list
        balls_to_remove = [ball for ball in self.balls if not ball.alive()]

        for ball in balls_to_remove:
            self.balls.remove(ball)

        # Check for Game Over condition
        if len(self.balls) == 0:
            self._show_game_over()

        super().update()

    def _show_game_over(self: Self) -> None:
        """Show the Game Over scene.

        Args:
            None

        Returns:
            None

        """
        self.next_scene = GameOverScene(options=self.options)
        self.previous_scene = self

    def _spawn_new_ball(self: Self, ball=None) -> None:
        """Spawn a new ball at random location with random direction.

        Args:
            ball: The ball that triggered the spawn (optional, for callback compatibility)

        Returns:
            None

        """
        # Create new ball at default speed
        new_ball = BallSprite(
            collision_sound=SFX.BOUNCE,
            bounce_top_bottom=True,   # Bounce off top and bottom walls
            bounce_left_right=False,  # Don't bounce off side walls (scoring)
            speed_up_mode=SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X,  # Logarithmic speed up on X only for paddle hits
            speed_up_multiplier=1.15,  # 15% speed increase
            speed_up_interval=1.0  # Not used for paddle-only mode
        )

        # Position the ball based on spawn mode
        if self.ball_spawn_mode & BallSpawnMode.RANDOM_POSITION:
            # Spawn at random location between the paddles and within top/bottom boundaries
            # Left paddle ends at x=20, right paddle starts at x=screen_width-20
            # So spawn between x=30 and x=screen_width-30 (with some margin)
            # And between y=20 and y=screen_height-20 (with some margin from top/bottom)
            # Try to find a location that's not too close to existing balls
            max_attempts = 10
            for attempt in range(max_attempts):
                spawn_x = secrets.randbelow(self.screen_width - 60) + 30  # Between paddles with margin
                spawn_y = secrets.randbelow(self.screen_height - 40) + 20  # Within top/bottom boundaries

                # Check if this location is far enough from existing balls
                min_distance = 100  # Minimum distance from other balls
                too_close = False
                for existing_ball in self.balls:
                    dx = spawn_x - existing_ball.rect.centerx
                    dy = spawn_y - existing_ball.rect.centery
                    distance = math.sqrt(dx * dx + dy * dy)
                    if distance < min_distance:
                        too_close = True
                        break

                if not too_close:
                    break

            new_ball.rect.x = spawn_x
            new_ball.rect.y = spawn_y
        else:
            # Fixed position (center of screen)
            new_ball.rect.x = self.screen_width // 2
            new_ball.rect.y = self.screen_height // 2

        # Set speed based on spawn mode
        if self.ball_spawn_mode & BallSpawnMode.RANDOM_SPEED:
            # Random direction with lower base speed for new balls
            # Ensure both X and Y speeds are non-zero by avoiding cardinal directions
            angle = secrets.randbelow(360) * (2 * math.pi / 360)
            base_speed = 150.0  # Lower speed for new balls
            
            # Calculate initial speeds
            speed_x = base_speed * math.cos(angle)
            speed_y = base_speed * math.sin(angle)
            
            # Ensure minimum speed in both directions (avoid zero speeds)
            min_speed = 50.0  # Minimum 50 pixels per second in each direction
            if abs(speed_x) < min_speed:
                speed_x = min_speed if speed_x >= 0 else -min_speed
            if abs(speed_y) < min_speed:
                speed_y = min_speed if speed_y >= 0 else -min_speed
                
            new_ball.speed = Speed(speed_x, speed_y)
        else:
            # Fixed speed (default ball speed)
            new_ball.speed = Speed(250.0, 125.0)

        # Set color based on spawn mode
        if self.ball_spawn_mode & BallSpawnMode.RANDOM_COLOR:
            new_ball.color = (secrets.randbelow(256), secrets.randbelow(256), secrets.randbelow(256))
        else:
            new_ball.color = WHITE
        # Add collision cooldown tracking
        new_ball.collision_cooldowns = {}
        # Set up paddle collision callback for ball spawn (with speed limit check)
        new_ball.on_paddle_collision = self._spawn_new_ball_with_speed_check

        # Add to balls list and sprite group
        self.balls.append(new_ball)
        self.all_sprites.add(new_ball)

    def _spawn_new_ball_with_speed_check(self: Self, ball) -> None:
        """Spawn a new ball based on configurable spawn mode.

        Args:
            ball: The ball that triggered the collision

        Returns:
            None
        """
        # Check if spawning is enabled
        if self.ball_spawn_mode == BallSpawnMode.NO_SPAWNING:
            return

        # Check cooldown if enabled
        if self.ball_spawn_mode & BallSpawnMode.COOLDOWN_ENABLED:
            current_time = time.time()
            cooldown = self._get_spawn_cooldown()
            if current_time - self.last_ball_spawn_time < cooldown:
                log.debug(f"Ball spawn cooldown active ({current_time - self.last_ball_spawn_time:.1f}s < {cooldown}s), not spawning")
                return

        # Check speed if enabled
        if self.ball_spawn_mode & BallSpawnMode.SPEED_CHECK_ENABLED:
            speed_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
            max_reasonable_speed = 1000.0  # 1000 pixels per second
            if speed_magnitude > max_reasonable_speed:
                log.debug(f"Ball speed too high ({speed_magnitude:.1f}), not spawning new ball")
                return

        # Spawn conditions met, spawn a new ball
        if self.ball_spawn_mode & BallSpawnMode.COOLDOWN_ENABLED:
            self.last_ball_spawn_time = time.time()
        self._spawn_new_ball()

    def _get_spawn_cooldown(self: Self) -> float:
        """Get the spawn cooldown based on the spawn mode.

        Returns:
            float: The cooldown time in seconds
        """
        if self.ball_spawn_mode & BallSpawnMode.FREQUENT:
            return 0.5
        elif self.ball_spawn_mode & BallSpawnMode.RARE:
            return 5.0
        else:  # NORMAL or default
            return 2.0

    def _handle_ball_collisions(self: Self) -> None:
        """Handle ball-to-ball collisions with proper physics.

        Args:
            None

        Returns:
            None

        """
        # Ball-to-ball collisions enabled

        # Check all pairs of balls for collisions
        for i in range(len(self.balls)):
            for j in range(i + 1, len(self.balls)):
                ball1 = self.balls[i]
                ball2 = self.balls[j]

                # Calculate distance between ball centers
                dx = ball2.rect.centerx - ball1.rect.centerx
                dy = ball2.rect.centery - ball1.rect.centery
                distance = math.sqrt(dx * dx + dy * dy)

                # Check if balls are colliding (sum of radii)
                collision_distance = ball1.rect.width // 2 + ball2.rect.width // 2

                # Skip if balls are too far apart or at exact same position
                if distance > collision_distance or distance < 0.001:
                    continue

                # No cooldown for ball-to-ball collisions - balls should be able to collide freely

                # Play collision sound
                if hasattr(ball1, "snd") and ball1.snd is not None:
                    ball1.snd.play()

                ball1_speed_before = math.sqrt(ball1.speed.x**2 + ball1.speed.y**2)
                ball2_speed_before = math.sqrt(ball2.speed.x**2 + ball2.speed.y**2)

                log.debug(
                    f"BALL-TO-BALL: ball1 speed before={ball1_speed_before:.2f}, "
                    f"ball2 speed before={ball2_speed_before:.2f}"
                )

                # Simple billiards-style collision
                # Calculate collision normal
                nx = dx / distance
                ny = dy / distance

                # Calculate relative velocity
                dvx = ball2.speed.x - ball1.speed.x
                dvy = ball2.speed.y - ball1.speed.y

                # Calculate relative velocity along collision normal
                dvn = dvx * nx + dvy * ny

                # Simplified collision logic: always allow collision if balls are overlapping
                # or if they're moving toward each other (dvn <= 0)
                if dvn > 0:
                    # Balls are moving away from each other - only allow collision if they're overlapping
                    # or if there's a significant speed difference (faster ball catching up)
                    ball1_speed_magnitude = math.sqrt(ball1.speed.x**2 + ball1.speed.y**2)
                    ball2_speed_magnitude = math.sqrt(ball2.speed.x**2 + ball2.speed.y**2)
                    
                    # Allow collision if balls are overlapping (distance < collision_distance)
                    # or if there's a significant speed difference
                    if distance >= collision_distance:
                        if ball1_speed_magnitude > 0 and ball2_speed_magnitude > 0:
                            speed_ratio = max(ball1_speed_magnitude, ball2_speed_magnitude) / min(ball1_speed_magnitude, ball2_speed_magnitude)
                            if speed_ratio < 1.2:  # Lower threshold for more collisions
                                continue  # Skip if speeds are too similar and balls aren't overlapping
                        else:
                            continue  # Skip if one ball has zero speed

                # Proper elastic collision physics for equal mass balls
                # Decompose velocities into normal and tangential components
                v1n_scalar = ball1.speed.x * nx + ball1.speed.y * ny
                v2n_scalar = ball2.speed.x * nx + ball2.speed.y * ny

                v1n_vec_x = v1n_scalar * nx
                v1n_vec_y = v1n_scalar * ny
                v2n_vec_x = v2n_scalar * nx
                v2n_vec_y = v2n_scalar * ny

                v1t_vec_x = ball1.speed.x - v1n_vec_x
                v1t_vec_y = ball1.speed.y - v1n_vec_y
                v2t_vec_x = ball2.speed.x - v2n_vec_x
                v2t_vec_y = ball2.speed.y - v2n_vec_y

                # Exchange normal components, preserve tangential components
                ball1.speed.x = v1t_vec_x + v2n_vec_x
                ball1.speed.y = v1t_vec_y + v2n_vec_y
                ball2.speed.x = v2t_vec_x + v1n_vec_x
                ball2.speed.y = v2t_vec_y + v1n_vec_y

                # Cap ball speeds to prevent runaway physics
                max_speed = 500.0  # Maximum speed in pixels per second
                for ball in [ball1, ball2]:
                    speed_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
                    if speed_magnitude > max_speed:
                        # Scale down the speed while preserving direction
                        scale_factor = max_speed / speed_magnitude
                        ball.speed.x *= scale_factor
                        ball.speed.y *= scale_factor

                # Calculate energy before and after for debugging
                energy_before = (ball1_speed_before**2 + ball2_speed_before**2)
                ball1_speed_after = math.sqrt(ball1.speed.x**2 + ball1.speed.y**2)
                ball2_speed_after = math.sqrt(ball2.speed.x**2 + ball2.speed.y**2)
                energy_after = (ball1_speed_after**2 + ball2_speed_after**2)

                log.debug(
                    f"BALL-TO-BALL: ball1 speed after={ball1_speed_after:.2f}, "
                    f"ball2 speed after={ball2_speed_after:.2f}, "
                    f"energy before={energy_before:.2f}, energy after={energy_after:.2f}"
                )

                # Separate balls to prevent sticking
                overlap = collision_distance - distance
                separation_distance = max(overlap, 2.0)  # Minimum 2px separation

                separation_x = nx * separation_distance * 0.5
                separation_y = ny * separation_distance * 0.5

                ball1.rect.x -= separation_x
                ball1.rect.y -= separation_y
                ball2.rect.x += separation_x
                ball2.rect.y += separation_y

                # No cooldown for ball-to-ball collisions - balls should be able to collide freely

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

        # Paddles continue moving until they hit boundaries - no key release handling needed

    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # Handle specific key presses instead of scanning all keys
        if event.key == pygame.K_SPACE:
            # Track that spacebar is pressed (but don't act on it yet)
            self._space_pressed = True
        elif event.key == pygame.K_w:
            log.debug(f"PADDLE: Player1 (left) UP - current_speed: {self.player1._move.current_speed}")
            self.player1.up()
        elif event.key == pygame.K_s:
            log.debug(f"PADDLE: Player1 (left) DOWN - current_speed: {self.player1._move.current_speed}")
            self.player1.down()
        elif event.key == pygame.K_UP:
            log.debug(f"PADDLE: Player2 (right) UP - current_speed: {self.player2._move.current_speed}")
            self.player2.up()
        elif event.key == pygame.K_DOWN:
            log.debug(f"PADDLE: Player2 (right) DOWN - current_speed: {self.player2._move.current_speed}")
            self.player2.down()

    def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        if event.key == pygame.K_SPACE and self._space_pressed:
            # Spacebar was pressed and now released - pause the game
            self._space_pressed = False
            self.pause()
        else:
            # Handle ESC/q to quit
            super().on_key_up_event(event)



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
