"""Enemy sprites for Brave Adventurer: Cobra, Scarab, and Scorpion.

Each draws its pose in dt_tick, after its state is decided and before the scene's collision
checks: their hitboxes are their visible pixels, so a pose drawn in update() (the render phase)
would be a frame late for collision (the pose rule, CLAUDE.md World Space). Each also draws its
first pose as it is made, so it has a hitbox before its first tick.
"""

from __future__ import annotations

from typing import Self, override

import pygame

from brave_adventurer.constants import (
    COBRA_HEIGHT,
    COBRA_WIDTH,
    SCARAB_HEIGHT,
    SCARAB_WIDTH,
    SCORPION_HEIGHT,
    SCORPION_WIDTH,
)
from brave_adventurer.drawing import draw_cobra, draw_scarab, draw_scorpion
from brave_adventurer_core.constants import GRAVITY, GROUND_Y, LAYER_ENEMIES, MAX_FALL_SPEED
from glitchygames.sprites import Sprite
from glitchygames.world import CoordinateSpace


class Cobra(Sprite):
    """A stationary cobra that bobs and periodically strikes.

    Cobras sit in one place and are always dangerous to touch.
    They animate with a gentle bob and a periodic strike lunge. A world sprite: the engine
    places it from the camera.
    """

    COORDINATE_SPACE = CoordinateSpace.WORLD

    STRIKE_INTERVAL = 2.0
    STRIKE_DURATION = 0.3

    def __init__(
        self,
        world_x: float,
        groups: pygame.sprite.LayeredDirty[Sprite],
    ) -> None:
        """Initialize a cobra enemy.

        Args:
            world_x: X position in world coordinates.
            groups: The sprite group to add this sprite to.

        """
        world_y = GROUND_Y - COBRA_HEIGHT
        self._layer = LAYER_ENEMIES

        super().__init__(
            x=world_x,
            y=world_y,
            width=COBRA_WIDTH,
            height=COBRA_HEIGHT,
            name='Cobra',
            groups=groups,
        )

        self.image = pygame.Surface((COBRA_WIDTH, COBRA_HEIGHT), pygame.SRCALPHA)

        self.world_x: float = world_x
        self.world_y: float = world_y
        self.strike_timer: float = 0.0
        self.striking: bool = False
        self.dirty = 2  # Always redraw (animation)
        self._draw_pose()

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Update the strike animation cycle.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        super().dt_tick(dt)
        self.strike_timer += dt

        if not self.striking and self.strike_timer >= self.STRIKE_INTERVAL:
            self.striking = True
            self.strike_timer = 0.0
        elif self.striking and self.strike_timer >= self.STRIKE_DURATION:
            self.striking = False
            self.strike_timer = 0.0

        self._draw_pose()

    def _draw_pose(self: Self) -> None:
        """Redraw the cobra with its current animation state."""
        self.image.fill((0, 0, 0, 0))
        draw_cobra(self.image, striking=self.striking, animation_timer=self.dt_timer)


class Scarab(Sprite):
    """A scarab beetle that rolls across the ground at constant speed.

    Scarabs roll in one direction, fall into pits (rolling on along the pit floor) and turn
    back at stone walls (the scene's terrain collision). A world sprite: the engine places it
    from the camera.
    """

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self,
        world_x: float,
        groups: pygame.sprite.LayeredDirty[Sprite],
        speed: float = -120.0,
    ) -> None:
        """Initialize a scarab beetle enemy.

        Args:
            world_x: Starting X position in world coordinates.
            groups: The sprite group to add this sprite to.
            speed: Horizontal speed in pixels/second (negative = moving left).

        """
        world_y = GROUND_Y - SCARAB_HEIGHT
        self._layer = LAYER_ENEMIES

        super().__init__(
            x=world_x,
            y=world_y,
            width=SCARAB_WIDTH,
            height=SCARAB_HEIGHT,
            name='Scarab',
            groups=groups,
        )

        self.image = pygame.Surface((SCARAB_WIDTH, SCARAB_HEIGHT), pygame.SRCALPHA)

        self.world_x: float = world_x
        self.world_y: float = world_y
        self.velocity_y: float = 0.0
        self.roll_speed: float = speed
        self.roll_angle: float = 0.0
        self.on_ground: bool = True
        self.dirty = 2  # Always redraw (rolling animation)
        self._draw_pose()

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Move the scarab with gravity and update roll animation.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        super().dt_tick(dt)

        # Gravity
        self.velocity_y = min(self.velocity_y + GRAVITY * dt, MAX_FALL_SPEED)
        self.world_y += self.velocity_y * dt

        # Horizontal movement
        self.world_x += self.roll_speed * dt
        self.roll_angle += abs(self.roll_speed) * dt * 0.1

        self._draw_pose()

    def _draw_pose(self: Self) -> None:
        """Redraw the scarab with its current roll angle."""
        self.image.fill((0, 0, 0, 0))
        draw_scarab(self.image, self.roll_angle)


class Scorpion(Sprite):
    """A scorpion that patrols back and forth within a range.

    Scorpions walk at a steady pace between their origin and origin + patrol_range,
    then reverse direction. A world sprite: the engine places it from the camera.
    """

    COORDINATE_SPACE = CoordinateSpace.WORLD

    DEFAULT_PATROL_SPEED = 60.0

    def __init__(
        self,
        world_x: float,
        groups: pygame.sprite.LayeredDirty[Sprite],
        patrol_range: float = 200.0,
    ) -> None:
        """Initialize a scorpion enemy.

        Args:
            world_x: Starting X position in world coordinates (also the patrol origin).
            groups: The sprite group to add this sprite to.
            patrol_range: How far the scorpion patrols from its origin.

        """
        world_y = GROUND_Y - SCORPION_HEIGHT
        self._layer = LAYER_ENEMIES

        super().__init__(
            x=world_x,
            y=world_y,
            width=SCORPION_WIDTH,
            height=SCORPION_HEIGHT,
            name='Scorpion',
            groups=groups,
        )

        self.image = pygame.Surface((SCORPION_WIDTH, SCORPION_HEIGHT), pygame.SRCALPHA)

        self.world_x: float = world_x
        self.world_y: float = world_y
        self.origin_x: float = world_x
        self.patrol_range: float = patrol_range
        self.patrol_speed: float = self.DEFAULT_PATROL_SPEED
        self.facing_right: bool = True
        self.dirty = 2  # Always redraw (moving)
        self._draw_pose()

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Move the scorpion along its patrol path.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        super().dt_tick(dt)

        direction = 1.0 if self.facing_right else -1.0
        self.world_x += self.patrol_speed * direction * dt

        # Reverse at patrol boundaries
        if self.world_x > self.origin_x + self.patrol_range:
            self.world_x = self.origin_x + self.patrol_range
            self.facing_right = False
        elif self.world_x < self.origin_x:
            self.world_x = self.origin_x
            self.facing_right = True

        self._draw_pose()

    def _draw_pose(self: Self) -> None:
        """Redraw the scorpion with its current facing direction."""
        self.image.fill((0, 0, 0, 0))
        draw_scorpion(self.image, facing_right=self.facing_right)
