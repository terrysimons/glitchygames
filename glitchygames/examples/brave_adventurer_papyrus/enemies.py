"""Papyrus Edition enemy sprites using TOML animation system."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.examples.brave_adventurer_papyrus.constants import (
    GROUND_Y,
    LAYER_ENEMIES,
    PAPYRUS_COBRA_HEIGHT,
    PAPYRUS_COBRA_WIDTH,
    PAPYRUS_SCARAB_HEIGHT,
    PAPYRUS_SCARAB_WIDTH,
    PAPYRUS_SCORPION_HEIGHT,
    PAPYRUS_SCORPION_WIDTH,
    SPRITES_DIR,
)
from glitchygames.examples.brave_adventurer_papyrus.sprite_utils import (
    apply_transparency_and_scale,
    prepare_papyrus_sprite,
)
from glitchygames.sprites import AnimatedSprite

if TYPE_CHECKING:
    from glitchygames.examples.brave_adventurer.camera import Camera


class PapyrusCobra(AnimatedSprite):
    """Cobra enemy using TOML sprite animations.

    Stationary cobra that bobs gently and periodically strikes.
    """

    STRIKE_INTERVAL = 2.0
    STRIKE_DURATION = 0.3

    def __init__(
        self,
        world_x: float,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Initialize the cobra.

        Args:
            world_x: X position in world coordinates.
            groups: The sprite group to add this sprite to.

        """
        self._layer = LAYER_ENEMIES

        super().__init__(
            filename=str(SPRITES_DIR / 'cobra.toml'),
            groups=groups,
        )
        prepare_papyrus_sprite(self)

        self.world_x: float = world_x
        self.world_y: float = GROUND_Y - PAPYRUS_COBRA_HEIGHT
        self.rect.x = round(self.world_x)
        self.rect.y = round(self.world_y)

        self.strike_timer: float = 0.0
        self.striking: bool = False

        self.play('idle')
        self.is_looping = True
        self.dirty = 2

    def dt_tick(self: Self, dt: float) -> None:
        """Update the strike animation cycle and advance frames.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        self.dt = dt
        self.strike_timer += dt

        if not self.striking and self.strike_timer >= self.STRIKE_INTERVAL:
            self.striking = True
            self.strike_timer = 0.0
            self.play('strike')
            self.is_looping = False
        elif self.striking and self.strike_timer >= self.STRIKE_DURATION:
            self.striking = False
            self.strike_timer = 0.0
            self.play('idle')
            self.is_looping = True

        AnimatedSprite.update(self, dt)
        apply_transparency_and_scale(self)

    def apply_camera(self, camera: Camera) -> None:
        """Update screen position from camera transform.

        Args:
            camera: The camera providing the world-to-screen transform.

        """
        screen_x, screen_y = camera.apply(self.world_x, self.world_y)
        self.rect.x = screen_x
        self.rect.y = screen_y

        if camera.is_visible(self.world_x, PAPYRUS_COBRA_WIDTH):
            self.visible = True
        else:
            self.visible = False
            self.dirty = 0

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """No-op. Animation is advanced in dt_tick() instead."""


class PapyrusScarab(AnimatedSprite):
    """Scarab beetle enemy using TOML sprite animations.

    Rolls across the ground at a constant speed.
    """

    def __init__(
        self,
        world_x: float,
        groups: pygame.sprite.LayeredDirty[Any],
        speed: float = -120.0,
    ) -> None:
        """Initialize the scarab.

        Args:
            world_x: Starting X position in world coordinates.
            groups: The sprite group to add this sprite to.
            speed: Horizontal speed in pixels/second (negative = moving left).

        """
        self._layer = LAYER_ENEMIES

        super().__init__(
            filename=str(SPRITES_DIR / 'scarab.toml'),
            groups=groups,
        )
        prepare_papyrus_sprite(self)

        self.world_x: float = world_x
        self.world_y: float = GROUND_Y - PAPYRUS_SCARAB_HEIGHT
        self.rect.x = round(self.world_x)
        self.rect.y = round(self.world_y)

        self.roll_speed: float = speed

        self.play('roll')
        self.is_looping = True
        self.dirty = 2

    def dt_tick(self: Self, dt: float) -> None:
        """Move the scarab and advance the roll animation.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        self.dt = dt
        self.world_x += self.roll_speed * dt
        AnimatedSprite.update(self, dt)
        apply_transparency_and_scale(self)

    def apply_camera(self, camera: Camera) -> None:
        """Update screen position from camera transform.

        Args:
            camera: The camera providing the world-to-screen transform.

        """
        screen_x, screen_y = camera.apply(self.world_x, self.world_y)
        self.rect.x = screen_x
        self.rect.y = screen_y

        if camera.is_visible(self.world_x, PAPYRUS_SCARAB_WIDTH):
            self.visible = True
        else:
            self.visible = False
            self.dirty = 0

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """No-op. Animation is advanced in dt_tick() instead."""


class PapyrusScorpion(AnimatedSprite):
    """Scorpion enemy using TOML sprite animations.

    Patrols back and forth within a range, flipping direction at boundaries.
    """

    DEFAULT_PATROL_SPEED = 60.0

    def __init__(
        self,
        world_x: float,
        groups: pygame.sprite.LayeredDirty[Any],
        patrol_range: float = 200.0,
    ) -> None:
        """Initialize the scorpion.

        Args:
            world_x: Starting X position in world coordinates (also patrol origin).
            groups: The sprite group to add this sprite to.
            patrol_range: How far the scorpion patrols from its origin.

        """
        self._layer = LAYER_ENEMIES

        super().__init__(
            filename=str(SPRITES_DIR / 'scorpion.toml'),
            groups=groups,
        )
        prepare_papyrus_sprite(self)

        self.world_x: float = world_x
        self.world_y: float = GROUND_Y - PAPYRUS_SCORPION_HEIGHT
        self.rect.x = round(self.world_x)
        self.rect.y = round(self.world_y)

        self.origin_x: float = world_x
        self.patrol_range: float = patrol_range
        self.patrol_speed: float = self.DEFAULT_PATROL_SPEED
        self.facing_right: bool = True

        self.play('walk')
        self.is_looping = True
        self.dirty = 2

    def dt_tick(self: Self, dt: float) -> None:
        """Move along patrol path and advance the walk animation.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        self.dt = dt

        direction = 1.0 if self.facing_right else -1.0
        self.world_x += self.patrol_speed * direction * dt

        # Reverse at patrol boundaries
        if self.world_x > self.origin_x + self.patrol_range:
            self.world_x = self.origin_x + self.patrol_range
            self.facing_right = False
        elif self.world_x < self.origin_x:
            self.world_x = self.origin_x
            self.facing_right = True

        AnimatedSprite.update(self, dt)
        apply_transparency_and_scale(self)

        # Flip image when facing left
        if not self.facing_right:
            self.image = pygame.transform.flip(self.image, flip_x=True, flip_y=False)

    def apply_camera(self, camera: Camera) -> None:
        """Update screen position from camera transform.

        Args:
            camera: The camera providing the world-to-screen transform.

        """
        screen_x, screen_y = camera.apply(self.world_x, self.world_y)
        self.rect.x = screen_x
        self.rect.y = screen_y

        if camera.is_visible(self.world_x, PAPYRUS_SCORPION_WIDTH):
            self.visible = True
        else:
            self.visible = False
            self.dirty = 0

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """No-op. Animation is advanced in dt_tick() instead."""
