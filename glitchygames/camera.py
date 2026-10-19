"""2D camera system for viewport tracking, world-to-screen conversion, and parallax.

Provides Camera2D for any scrolling game. Supports smooth follow,
world bounds clamping, visibility culling, and built-in parallax
background layer management.

Promoted from brave_adventurer/camera.py and parallax.py into the
engine so every game gets viewport support for free.
"""

from __future__ import annotations

import enum
import logging
import math
from typing import TYPE_CHECKING, Self, override

import pygame

from glitchygames.effects.shake import ScreenShake
from glitchygames.pixel_snap import active_default_snap_mode, snap_to_pixel
from glitchygames.sprites import Sprite

if TYPE_CHECKING:
    from collections.abc import Callable

log: logging.Logger = logging.getLogger('game.camera')

# Threshold for comparing scroll factors to zero
STATIC_SCROLL_THRESHOLD = 1e-9

# Default smooth follow factor (0.0 = no movement, 1.0 = instant snap)
DEFAULT_SMOOTH_FACTOR = 0.1

# Default visibility culling margin in pixels
DEFAULT_VISIBILITY_MARGIN = 64.0

# Reference frame rate for frame-rate-independent smoothing
REFERENCE_FPS = 60.0


class FollowAxes(enum.Flag):
    """Which camera axes follow the target; an unfollowed axis keeps the camera where it is."""

    X = enum.auto()
    Y = enum.auto()
    BOTH = X | Y


class ParallaxLayer(Sprite):
    """A full-screen background layer that scrolls relative to the camera.

    Scrolls at `scroll_factor` times the camera speed, creating depth
    illusion. Static layers (scroll_factor ~0) render once; scrolling
    layers redraw every frame.
    """

    def __init__(
        self,
        *,
        scroll_factor: float,
        draw_function: Callable[[pygame.Surface, float, float], None],
        layer_depth: int,
        groups: pygame.sprite.LayeredDirty[Sprite],
        screen_width: int,
        screen_height: int,
    ) -> None:
        """Initialize a parallax background layer.

        Args:
            scroll_factor: Scroll rate relative to camera (0.0=static, 1.0=foreground).
            draw_function: Callable(surface, camera_x, camera_y) that draws the layer.
            layer_depth: Z-layer for rendering order (lower = further back).
            groups: The sprite group to add this layer to.
            screen_width: Width of the display.
            screen_height: Height of the display.

        """
        super().__init__(
            x=0,
            y=0,
            width=screen_width,
            height=screen_height,
            name=f'ParallaxLayer_{layer_depth}',
            groups=groups,
        )

        self.image = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        self.scroll_factor = scroll_factor
        self.draw_function = draw_function
        self.is_static = math.isclose(
            scroll_factor,
            0.0,
            abs_tol=STATIC_SCROLL_THRESHOLD,
        )

        groups.change_layer(self, layer_depth)

        if self.is_static:
            self.dirty = 1
            self.draw_function(self.image, 0.0, 0.0)
        else:
            self.dirty = 2

    def update_scroll(self, camera_x: float, camera_y: float) -> None:
        """Recalculate the parallax offset and redraw the layer.

        Args:
            camera_x: The camera's current world X position.
            camera_y: The camera's current world Y position.

        """
        if self.is_static:
            return

        offset_x = camera_x * self.scroll_factor
        offset_y = camera_y * self.scroll_factor
        self.image.fill((0, 0, 0, 0))
        self.draw_function(self.image, offset_x, offset_y)

    @override
    def update(self: Self) -> None:
        """No-op. Drawing is handled by update_scroll()."""


class Camera2D:
    """2D viewport camera with smooth follow, bounds, and parallax.

    Tracks a target position with configurable lead offset and smooth
    interpolation. Converts world coordinates to screen coordinates
    for rendering. Manages parallax background layers.

    Args:
        screen_width: Viewport width in pixels.
        screen_height: Viewport height in pixels.
        smooth_factor: Follow responsiveness (0.0=frozen, 1.0=instant).
        lead_x: Horizontal offset from target to viewport left edge.
        lead_y: Vertical offset from target to viewport top edge.
        visibility_margin: Extra pixels around viewport for culling checks.
        shake_intensity: Player setting 0.0-1.0 scaling world shake (0 disables it).

    """

    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        *,
        smooth_factor: float = DEFAULT_SMOOTH_FACTOR,
        lead_x: float = 0.0,
        lead_y: float = 0.0,
        visibility_margin: float = DEFAULT_VISIBILITY_MARGIN,
        shake_intensity: float = 1.0,
    ) -> None:
        """Initialize the camera."""
        self.world_x: float = 0.0
        self.world_y: float = 0.0
        self.screen_width: int = screen_width
        self.screen_height: int = screen_height
        self.smooth_factor: float = smooth_factor
        self.lead_x: float = lead_x
        self.lead_y: float = lead_y
        self.visibility_margin: float = visibility_margin

        # Shake moves world sprites only; world_x/world_y stay unshaken for logic
        self.shake_effect: ScreenShake = ScreenShake(intensity=shake_intensity)

        # World bounds (None = unbounded in that direction)
        self._min_x: float | None = None
        self._min_y: float | None = None
        self._max_x: float | None = None
        self._max_y: float | None = None

        # Parallax layers
        self._parallax_layers: list[ParallaxLayer] = []

        # Set by apply(); WORLD shake only moves sprites positioned through apply()
        self._has_been_applied: bool = False

        # Declared follow target (see follow()); the engine aims the camera at it each frame
        self._follow_target: object | None = None
        self._follow_axes: FollowAxes = FollowAxes.BOTH

        # Set when game code calls update() this frame (cleared by begin_frame()), so the
        # engine can warn when the game and the engine both move the camera in one frame
        self._updated_by_game_this_frame: bool = False

        # Set whenever the WORLD shake advances (cleared by begin_frame()), so the engine
        # advances it exactly once per frame whoever moves the camera, or when nobody does
        self._shake_advanced_this_frame: bool = False

    @property
    def follow_target(self: Self) -> object | None:
        """The world sprite the engine aims the camera at, or None (manual camera)."""
        return self._follow_target

    @property
    def follow_axes(self: Self) -> FollowAxes:
        """The axes that follow the target; the others keep the camera where it is."""
        return self._follow_axes

    def follow(self: Self, *, target: object | None, axes: FollowAxes = FollowAxes.BOTH) -> None:
        """Declare the world sprite the engine aims this camera at each frame.

        The target needs world_x and world_y. The scene's camera_target() hook reads it, and
        the engine applies the axes to whichever point that hook supplies.

        The camera holds the target strongly. A target that is killed or removed from its
        groups keeps the camera aimed at its last position; call follow(target=...) again with
        the new sprite on respawn. follow(target=None) also resets the axes to
        FollowAxes.BOTH unless axes is passed.

        Args:
            target: The sprite to follow, or None to stop following (manual camera).
            axes: The axes that follow (FollowAxes.X, FollowAxes.Y or FollowAxes.BOTH).

        """
        self._follow_target = target
        self._follow_axes = axes

    @property
    def updated_by_game_this_frame(self: Self) -> bool:
        """Whether game code called update() since the last begin_frame()."""
        return self._updated_by_game_this_frame

    @property
    def shake_advanced_this_frame(self: Self) -> bool:
        """Whether the WORLD shake advanced since the last begin_frame()."""
        return self._shake_advanced_this_frame

    def aim_at(self: Self, *, target_x: float, target_y: float, dt: float) -> None:
        """Move toward a target on the followed axes only (the engine's camera aim).

        An axis not in follow_axes aims at the camera's current goal on that axis
        (world position plus lead offset), so smoothing leaves it where it is and only the
        bounds clamp applies. Does not count as a game update(). The WORLD shake is not
        advanced again if game code already advanced it this frame (a camera.update() in
        dt_tick while the engine also aims), so it advances once per frame.

        Args:
            target_x: Target X position in world coordinates.
            target_y: Target Y position in world coordinates.
            dt: Delta time in seconds since last frame.

        """
        target_x, target_y = self._target_on_followed_axes(target_x=target_x, target_y=target_y)
        self._engine_update(
            target_x=target_x,
            target_y=target_y,
            dt=dt,
            advance_shake=not self._shake_advanced_this_frame,
        )

    def snap_followed_axes_to(self: Self, *, target_x: float, target_y: float) -> None:
        """Instantly move to a target on the followed axes only (snap_to, honouring the axes).

        An axis not in follow_axes keeps the camera where it is (only the bounds clamp
        applies), as aim_at() does. The engine uses this for a transition's arriving-scene
        screenshot, so a side-scroller's camera keeps its y.

        Args:
            target_x: Target X in world coordinates.
            target_y: Target Y in world coordinates.

        """
        target_x, target_y = self._target_on_followed_axes(target_x=target_x, target_y=target_y)
        self.snap_to(target_x=target_x, target_y=target_y)

    def _target_on_followed_axes(
        self: Self, *, target_x: float, target_y: float
    ) -> tuple[float, float]:
        """Replace the target on each unfollowed axis with the camera's current goal there.

        The current goal is the world position plus the lead offset, so moving toward it
        (smoothed or snapped) leaves the camera where it is on that axis.

        Args:
            target_x: Target X in world coordinates.
            target_y: Target Y in world coordinates.

        Returns:
            tuple[float, float]: The target to move toward.

        """
        if FollowAxes.X not in self._follow_axes:
            target_x = self.world_x + self.lead_x
        if FollowAxes.Y not in self._follow_axes:
            target_y = self.world_y + self.lead_y
        return (target_x, target_y)

    def advance_shake(self: Self, *, dt: float) -> None:
        """Advance the WORLD shake without moving the camera (the engine's still-camera step).

        The engine calls this at the end of a frame in which nothing moved the camera (no
        engine aim, no game update()), so a shake on a camera that stands still (a scene that
        never scrolls, or a follow game after game over) still decays and its rumble stops.
        The camera position does not change, so parallax layers do not scroll; while a shake
        is running they are redrawn from the same position with the new shake offset, so
        their shake displacement follows the shake and returns to rest with it.

        Args:
            dt: Delta time in seconds (the scene's dt, as the engine aim would have used).

        """
        shake_was_active = self.shake_effect.is_active
        self.shake_effect.update(dt)
        self._shake_advanced_this_frame = True
        if shake_was_active:
            shake_x, shake_y = self.shake_effect.offset
            self._update_parallax_layers(
                camera_x=self.world_x + shake_x, camera_y=self.world_y + shake_y
            )

    def begin_frame(self: Self) -> None:
        """Start a new frame: forget last frame's game update() and WORLD shake advance."""
        self._updated_by_game_this_frame = False
        self._shake_advanced_this_frame = False

    @property
    def has_been_applied(self: Self) -> bool:
        """Whether apply() has ever been called (some sprite is positioned through this camera).

        Returns:
            True once apply() has been called at least once.

        """
        return self._has_been_applied

    @property
    def has_parallax_layers(self: Self) -> bool:
        """Whether the camera scrolls any background (parallax) layers.

        Returns:
            True once add_background_layer() has added a layer.

        """
        return bool(self._parallax_layers)

    @property
    def bounds(self) -> tuple[float | None, float | None, float | None, float | None]:
        """World bounds as (min_x, min_y, max_x, max_y); None means unbounded on that edge."""
        return (self._min_x, self._min_y, self._max_x, self._max_y)

    def set_bounds(
        self,
        *,
        min_x: float | None = None,
        min_y: float | None = None,
        max_x: float | None = None,
        max_y: float | None = None,
    ) -> None:
        """Set world bounds to clamp camera position.

        Pass None for any edge to leave it unbounded.

        Args:
            min_x: Minimum camera X (left boundary).
            min_y: Minimum camera Y (top boundary).
            max_x: Maximum camera X (right boundary).
            max_y: Maximum camera Y (bottom boundary).

        """
        self._min_x = min_x
        self._min_y = min_y
        self._max_x = max_x
        self._max_y = max_y

    def update(self, target_x: float, target_y: float, dt: float) -> None:
        """Smoothly move the camera toward the target position.

        Uses frame-rate-independent exponential smoothing. The lead
        offset is subtracted from the target so the tracked object
        appears at that offset from the viewport edge.

        This is the manual-camera call for game code. A camera the engine aims (a follow
        target or a camera_target() hook) should not also be updated by the game.

        Args:
            target_x: Target X position in world coordinates.
            target_y: Target Y position in world coordinates.
            dt: Delta time in seconds since last frame.

        """
        self._updated_by_game_this_frame = True
        self._engine_update(target_x=target_x, target_y=target_y, dt=dt)

    def _engine_update(
        self, *, target_x: float, target_y: float, dt: float, advance_shake: bool = True
    ) -> None:
        """Move the camera exactly as update() does, without marking a game update.

        Called by update() and by aim_at() (the engine's camera aim,
        glitchygames.world.aim_camera).

        Args:
            target_x: Target X position in world coordinates.
            target_y: Target Y position in world coordinates.
            dt: Delta time in seconds since last frame.
            advance_shake: Whether to advance the WORLD shake by dt (False when it already
                advanced this frame).

        """
        goal_x = target_x - self.lead_x
        goal_y = target_y - self.lead_y

        # Frame-rate-independent exponential smoothing
        smoothing = 1.0 - (1.0 - self.smooth_factor) ** (dt * REFERENCE_FPS)

        self.world_x += (goal_x - self.world_x) * smoothing
        self.world_y += (goal_y - self.world_y) * smoothing

        # Clamp to world bounds
        self._clamp_to_bounds()

        if advance_shake:
            self.shake_effect.update(dt)
            self._shake_advanced_this_frame = True
        shake_x, shake_y = self.shake_effect.offset
        # Layers scroll from the shaken position, so each shakes in proportion to its
        # scroll_factor: a static sky never shakes, distant scenery barely moves.
        self._update_parallax_layers(
            camera_x=self.world_x + shake_x, camera_y=self.world_y + shake_y
        )

    def snap_to(self, target_x: float, target_y: float) -> None:
        """Instantly move the camera to target position (no smoothing).

        Useful for scene setup, transitions, and teleports where
        the camera should not lerp.

        Args:
            target_x: Target X in world coordinates.
            target_y: Target Y in world coordinates.

        """
        self.world_x = target_x - self.lead_x
        self.world_y = target_y - self.lead_y
        self._clamp_to_bounds()

        self._update_parallax_layers(camera_x=self.world_x, camera_y=self.world_y)

    def _update_parallax_layers(self, *, camera_x: float, camera_y: float) -> None:
        """Scroll every parallax layer to the given camera position, snapped to whole pixels.

        The position is snapped with the active default snap mode (the scene's
        PIXEL_SNAP_MODE), the same snapped camera position world sprites are drawn from, so
        the background never shimmers against them.

        Args:
            camera_x: Camera X used for the parallax offset.
            camera_y: Camera Y used for the parallax offset.

        """
        mode = active_default_snap_mode()
        snapped_camera_x = snap_to_pixel(camera_x, mode)
        snapped_camera_y = snap_to_pixel(camera_y, mode)
        for layer in self._parallax_layers:
            layer.update_scroll(snapped_camera_x, snapped_camera_y)

    def _clamp_to_bounds(self) -> None:
        """Clamp camera position to configured world bounds."""
        if self._min_x is not None:
            self.world_x = max(self.world_x, self._min_x)
        if self._min_y is not None:
            self.world_y = max(self.world_y, self._min_y)
        if self._max_x is not None:
            self.world_x = min(self.world_x, self._max_x)
        if self._max_y is not None:
            self.world_y = min(self.world_y, self._max_y)

    def apply(self, world_x: float, world_y: float) -> tuple[int, int]:
        """Convert world coordinates to screen coordinates.

        Args:
            world_x: X position in world space.
            world_y: Y position in world space.

        Returns:
            A tuple of (screen_x, screen_y) pixel coordinates.

        """
        self._has_been_applied = True
        return self.world_to_screen(world_x, world_y)

    def world_to_screen(self, world_x: float, world_y: float) -> tuple[int, int]:
        """Convert world coordinates to screen coordinates without side effects.

        Uses the same math as apply(), including the WORLD shake offset, but does not mark
        the camera as applied. Intended for read-only tools such as the debug overlay.

        Args:
            world_x: X position in world space.
            world_y: Y position in world space.

        Returns:
            A tuple of (screen_x, screen_y) pixel coordinates.

        """
        shake_x, shake_y = self.shake_effect.offset
        return (
            round(world_x - self.world_x - shake_x),
            round(world_y - self.world_y - shake_y),
        )

    def is_visible(
        self,
        world_x: float,
        width: float,
        world_y: float = 0.0,
        height: float = 0.0,
    ) -> bool:
        """Check if a world-space object overlaps the visible viewport.

        Uses a configurable margin so sprites are drawn just before
        scrolling into view.

        Args:
            world_x: Left edge X in world space.
            width: Object width.
            world_y: Top edge Y in world space (0.0 for X-only check).
            height: Object height (0.0 for X-only check).

        Returns:
            True if the object overlaps the visible area (with margin).

        """
        margin = self.visibility_margin

        # X-axis check
        x_visible = (
            world_x + width > self.world_x - margin
            and world_x < self.world_x + self.screen_width + margin
        )

        # Y-axis check (skip if height is 0, for backward compatibility)
        if height == 0.0:  # ruff: ignore[float-equality-comparison] - exact zero means "X-only check"
            return x_visible

        y_visible = (
            world_y + height > self.world_y - margin
            and world_y < self.world_y + self.screen_height + margin
        )

        return x_visible and y_visible

    def add_background_layer(
        self,
        *,
        scroll_factor: float,
        draw_function: Callable[[pygame.Surface, float, float], None],
        layer_depth: int,
        groups: pygame.sprite.LayeredDirty[Sprite],
        screen_width: int | None = None,
        screen_height: int | None = None,
    ) -> ParallaxLayer:
        """Add a parallax background layer managed by this camera.

        Args:
            scroll_factor: Scroll rate (0.0=static, 1.0=foreground speed).
            draw_function: Callable(surface, camera_x, camera_y) that draws the layer.
            layer_depth: Z-layer for rendering order (lower = further back).
            groups: Sprite group for the layer.
            screen_width: Layer width (defaults to camera viewport width).
            screen_height: Layer height (defaults to camera viewport height).

        Returns:
            The created ParallaxLayer.

        """
        layer = ParallaxLayer(
            scroll_factor=scroll_factor,
            draw_function=draw_function,
            layer_depth=layer_depth,
            groups=groups,
            screen_width=screen_width or self.screen_width,
            screen_height=screen_height or self.screen_height,
        )
        self._parallax_layers.append(layer)
        return layer
