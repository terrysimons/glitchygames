"""Main game scene for Clockwork Keep — a steampunk tower climb."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.audio.exceptions import AudioUnavailableError
from glitchygames.audio.recipes import SoundBank, Tremolo
from glitchygames.audio.synth import Waveform
from glitchygames.camera import Camera2D, FollowAxes
from glitchygames.collision.layers import collision_rect_offset, get_sprite_collision_rect
from glitchygames.effects.shake import RumbleSettings, Shake, ShakeAxis, ShakeStyle, ShakeTarget
from glitchygames.engine import GameEngine
from glitchygames.examples.clockwork_keep.constants import (
    BOILER_LED,
    BOILER_PLATFORM,
    BOILER_PLATFORM_TOP,
    CAMERA_LEAD_X,
    CAMERA_LEAD_Y,
    CLOCK_LED,
    CLOCK_PLATFORM,
    CLOCK_PLATFORM_TOP,
    CLOCK_START_SECONDS,
    COG_BRONZE_POINTS,
    COG_GOLD_POINTS,
    COG_SILVER_POINTS,
    COG_SIZE,
    ELEVATOR_ASCENT_RUMBLE_HIGH,
    ELEVATOR_ASCENT_RUMBLE_LOW,
    ELEVATOR_BOUNCE_DURATION,
    ELEVATOR_BOUNCE_FREQUENCY,
    ELEVATOR_BOUNCE_STRENGTH,
    ELEVATOR_MOTOR_IDLE_FREQUENCY,
    ELEVATOR_MOTOR_LOW_PASS_CUTOFF,
    ELEVATOR_MOTOR_MAXIMUM_VOLUME,
    ELEVATOR_MOTOR_MINIMUM_VOLUME,
    ELEVATOR_MOTOR_PEAK_FREQUENCY,
    ELEVATOR_MOTOR_TREMOLO_DEPTH,
    ELEVATOR_MOTOR_TREMOLO_RATE,
    ELEVATOR_RATTLE_DURATION,
    ELEVATOR_RATTLE_FREQUENCY,
    ELEVATOR_RATTLE_STRENGTH,
    ELEVATOR_RIDE_DURATION,
    ELEVATOR_RIDE_EASING,
    ELEVATOR_SNAP_TOLERANCE,
    ELEVATOR_SPEED_SAMPLES,
    GEAR_LED,
    GEAR_PLATFORM,
    GEAR_PLATFORM_TOP,
    GROUND_SNAP_TOLERANCE,
    HUD_SHADOW_COLOR,
    HUD_TEXT_COLOR,
    LAYER_COLLECTIBLES,
    LAYER_FAR_BACKGROUND,
    PARALLAX_FAR,
    PIT_DEATH_THRESHOLD,
)
from glitchygames.examples.clockwork_keep.drawing import (
    draw_boiler_background,
    draw_clock_background,
    draw_cog_collectible,
    draw_gear_background,
)
from glitchygames.examples.clockwork_keep.levels import ALL_FLOORS, FloorData
from glitchygames.examples.clockwork_keep.player import Tinker
from glitchygames.examples.clockwork_keep.sounds import ALL_RECIPES
from glitchygames.examples.clockwork_keep.terrain import Elevator, MovingGear, Platform
from glitchygames.input import ActionMap
from glitchygames.scenes import Scene
from glitchygames.scenes.builtin_scenes.game_over_scene import GameOverScene, TextSprite
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.sprites import Sprite
from glitchygames.state import SaveManager, SaveNotFoundError, open_saves
from glitchygames.transitions import ElevatorTransition, FadeTransition
from glitchygames.world import CoordinateSpace

if TYPE_CHECKING:
    import argparse

    from glitchygames.audio.live import LiveVoice
    from glitchygames.events.base import (
        ControllerButtonEvent,
        JoyAxisEvent,
        JoyButtonEvent,
        KeyEvent,
        WindowEvent,
    )
    from glitchygames.transitions import Transition

log = logging.getLogger('game')

# Background drawing functions per floor
_FLOOR_BACKGROUNDS = [
    draw_boiler_background,
    draw_gear_background,
    draw_clock_background,
]

# Theme colors per floor: (platform_color, top_color, led_color)
_FLOOR_THEMES: list[tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]] = [
    (BOILER_PLATFORM, BOILER_PLATFORM_TOP, BOILER_LED),
    (GEAR_PLATFORM, GEAR_PLATFORM_TOP, GEAR_LED),
    (CLOCK_PLATFORM, CLOCK_PLATFORM_TOP, CLOCK_LED),
]

# Arrival shakes: the car slams into the floor, then the cage rattles
ELEVATOR_STOP_BOUNCE = Shake(
    style=ShakeStyle.BOUNCE,
    strength=ELEVATOR_BOUNCE_STRENGTH,
    duration=ELEVATOR_BOUNCE_DURATION,
    frequency=ELEVATOR_BOUNCE_FREQUENCY,
    axis=ShakeAxis.VERTICAL,
    rumble=RumbleSettings(low_frequency=1.0, high_frequency=0.5, scale_with_strength=False),
)
ELEVATOR_STOP_RATTLE = Shake(
    style=ShakeStyle.NOISE,
    strength=ELEVATOR_RATTLE_STRENGTH,
    duration=ELEVATOR_RATTLE_DURATION,
    frequency=ELEVATOR_RATTLE_FREQUENCY,
    rumble=RumbleSettings(low_frequency=0.4, high_frequency=0.8, scale_with_strength=False),
)

# Cog colors and points
_COG_TYPES: dict[str, tuple[tuple[int, int, int], int]] = {
    'bronze': ((180, 120, 50), COG_BRONZE_POINTS),
    'silver': ((180, 180, 190), COG_SILVER_POINTS),
    'gold': ((220, 190, 50), COG_GOLD_POINTS),
}


class CogCollectible(Sprite):
    """A collectible cog with bobbing animation.

    Args:
        world_x: X position in world space.
        world_y: Y position in world space.
        cog_type: One of 'bronze', 'silver', 'gold'.
        groups: Sprite group to add to.

    """

    # A world sprite: the engine places it from the camera
    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self,
        world_x: float,
        world_y: float,
        cog_type: str,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Initialize the cog collectible."""
        self._layer = LAYER_COLLECTIBLES
        super().__init__(
            x=world_x,
            y=world_y,
            width=COG_SIZE,
            height=COG_SIZE,
            name='Cog',
            groups=groups,
        )
        self.world_x = world_x
        self._base_world_y = world_y
        self.world_y = world_y
        self.cog_type = cog_type
        self.color, self.points = _COG_TYPES.get(cog_type, _COG_TYPES['bronze'])
        self.image = pygame.Surface((COG_SIZE, COG_SIZE), pygame.SRCALPHA)
        self._timer: float = 0.0
        self.dirty = 2

    @override
    def dt_tick(self, dt: float) -> None:
        """Bob the sprite position and spin the gear teeth.

        Args:
            dt: Delta time in seconds.

        """
        self._timer += dt
        # Bob by moving world_y, not by shifting pixels inside the surface
        bob_offset = math.sin(self._timer * 3.0) * 3.0
        self.world_y = self._base_world_y + bob_offset
        # Redraw with spinning teeth
        self.image.fill((0, 0, 0, 0))
        draw_cog_collectible(self.image, self.color, rotation=self._timer * 0.5)


class ClockworkKeepScene(Scene):
    """One floor of the clockwork tower.

    Each floor is a separate Scene instance. Elevators trigger
    scene transitions to the next floor.
    """

    NAME = 'Clockwork Keep'
    VERSION = '1.0'
    # Cap dt so a hitch (focus loss, Cmd-Tab, ...) advances the game at most 50 ms (20 fps).
    # The engine caps the dt dt_tick and the camera aim receive. A capped tick still moves a
    # falling Tinker 40 px, so the ground check sweeps the fall (_resolve_ground_collision)
    # rather than relying on the cap to keep it from passing through a platform
    MAX_FRAME_SECONDS = 0.05

    def __init__(
        self: Self,
        floor_index: int | None = None,
        player_score: int = 0,
        player_lives: int = 3,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize the floor scene.

        Args:
            floor_index: Which floor (0=Boiler Room, 1=Gear Works, 2=Clock Face). None (the
                engine's first scene, built from options alone) takes the --floor option.
            player_score: Score carried from previous floor.
            player_lives: Lives carried from previous floor.
            options: Command-line options.
            groups: Sprite group.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(options=options, groups=groups)

        self.floor_index = self._starting_floor_index(floor_index=floor_index, options=options)
        # The score and lives carried onto this floor, as it began (replay_arguments)
        self.starting_player_score = player_score
        self.starting_player_lives = player_lives
        self.floor_data: FloorData = ALL_FLOORS[self.floor_index]
        # Game time on this floor (capped dt, frozen after game over); drives the floor-3 clock
        self.floor_elapsed_time: float = 0.0

        # Theme colors
        platform_color, top_color, self.led_color = _FLOOR_THEMES[self.floor_index]

        # Background
        bg_color = [
            (40, 25, 15),  # Boiler Room
            (35, 35, 40),  # Gear Works
            (15, 15, 35),  # Clock Face
        ][self.floor_index]
        self.background_color = bg_color

        # Camera: vertical scroll only (tower is 1 screen wide)
        self.camera = Camera2D(
            screen_width=self.screen_width,
            screen_height=self.screen_height,
            lead_x=CAMERA_LEAD_X,
            lead_y=CAMERA_LEAD_Y,
            shake_intensity=self.options.get('screen_shake_intensity', 1.0),
        )
        self.camera.set_bounds(
            min_x=0.0,
            max_x=0.0,  # No horizontal scroll
            min_y=0.0,
            max_y=float(self.floor_data.height - self.screen_height),
        )

        # Background parallax
        shows_clock = _FLOOR_BACKGROUNDS[self.floor_index] is draw_clock_background
        bg_func = (
            self._draw_timed_clock_background
            if shows_clock
            else _FLOOR_BACKGROUNDS[self.floor_index]
        )
        self.camera.add_background_layer(
            scroll_factor=PARALLAX_FAR,
            draw_function=bg_func,
            layer_depth=LAYER_FAR_BACKGROUND,
            groups=self.all_sprites,
            # The clock's hands show the floor's elapsed game time, not just the camera offset,
            # so that layer redraws every frame; the other floors' walls depend on camera_y only
            animated=shows_clock,
        )

        # Build terrain (in this order: sprites of one layer draw in the order they are added)
        self.platform_sprites: list[Platform] = self._build_platforms(
            platform_color=platform_color, top_color=top_color
        )
        self.elevator_sprites: list[Elevator] = self._build_elevators()
        self.moving_gear_sprites: list[MovingGear] = self._build_moving_gears()
        self.collectible_sprites: list[CogCollectible] = self._build_collectibles()

        # Player
        self.player = Tinker(
            world_x=float(self.floor_data.spawn_x),
            world_y=float(self.floor_data.spawn_y),
            groups=self.all_sprites,
        )
        self.player.score = player_score
        self.player.lives = player_lives
        self.player.floor = self.floor_index

        # Collision layers: cog pickups (and the debug overlay) use these collision rects
        self.collisions.add_layer('player').add(self.player)
        cog_layer = self.collisions.add_layer('cogs')
        for cog in self.collectible_sprites:
            cog_layer.add(cog)

        # Game state
        self.game_over_triggered: bool = False
        # The moving gear the player stood on after the last ground collision, if any
        self.riding_gear: MovingGear | None = None
        # The platform the player stood on after the last ground collision, if any
        self.supporting_platform: Platform | None = None
        # The top floor's highest platform: standing on it wins the game (None on the floors
        # below, which an elevator leaves)
        self.victory_platform: Platform | None = self._find_victory_platform()
        # Where the player's world y was before this tick moved it: the ground check sweeps
        # the fall from there (None outside dt_tick: no sweep)
        self._player_world_y_before_tick: float | None = None

        # Sound
        self.sounds = SoundBank(ALL_RECIPES)
        self._was_grounded: bool | None = None  # Set from the first real collision result
        self._elevator_motor: LiveVoice | None = None
        self._elevator_peak_velocity = 1.0

        # Persistence
        self.saves: SaveManager = open_saves(app_name='clockwork-keep')

        # Input
        self.actions = self._create_action_map(input_mode=self.options.get('input_mode', 'auto'))

        # HUD
        self.hud_font: pygame.font.Font | None = None

    def _build_platforms(
        self: Self, *, platform_color: tuple[int, int, int], top_color: tuple[int, int, int]
    ) -> list[Platform]:
        """Build the floor's platforms from its level data.

        Args:
            platform_color: The floor theme's platform body color.
            top_color: The floor theme's platform top edge color.

        Returns:
            The platforms, in level-data order.

        """
        return [
            Platform(
                world_x=float(platform_x),
                world_y=float(platform_y),
                width=platform_width,
                platform_color=platform_color,
                top_color=top_color,
                groups=self.all_sprites,
            )
            for platform_x, platform_y, platform_width in self.floor_data.platforms
        ]

    def _build_elevators(self: Self) -> list[Elevator]:
        """Build the floor's elevators from its level data.

        Returns:
            The elevators, in level-data order.

        """
        return [
            Elevator(world_x=float(elevator_x), world_y=float(elevator_y), groups=self.all_sprites)
            for elevator_x, elevator_y in self.floor_data.elevators
        ]

    def _build_moving_gears(self: Self) -> list[MovingGear]:
        """Build the floor's moving gear platforms from its level data.

        Returns:
            The moving gears, in level-data order.

        """
        return [
            MovingGear(
                world_x=float(gear_data.world_x),
                world_y=float(gear_data.world_y),
                groups=self.all_sprites,
                move_range_x=gear_data.move_range_x,
                move_range_y=gear_data.move_range_y,
                speed=gear_data.speed,
                size=gear_data.size,
            )
            for gear_data in self.floor_data.moving_gears
        ]

    def _build_collectibles(self: Self) -> list[CogCollectible]:
        """Build the floor's cogs from its level data.

        Returns:
            The cogs, in level-data order.

        """
        return [
            CogCollectible(
                world_x=float(cog_x),
                world_y=float(cog_y),
                cog_type=cog_type,
                groups=self.all_sprites,
            )
            for cog_x, cog_y, cog_type in self.floor_data.collectibles
        ]

    def _find_victory_platform(self: Self) -> Platform | None:
        """Return the platform that wins the game: the top floor's highest one.

        Returns:
            The victory platform, or None on a floor below the top.

        """
        if self.floor_index < len(ALL_FLOORS) - 1:
            return None
        return min(self.platform_sprites, key=lambda platform: platform.world_y)

    @staticmethod
    def _starting_floor_index(*, floor_index: int | None, options: dict[str, Any] | None) -> int:
        """Return the floor to build: the one named, else the --floor option (BUGS.md #79).

        Args:
            floor_index: The floor the caller names (the elevator, a playback's rebuild), or None
                for the engine's first scene, which it builds from options alone.
            options: Command-line options.

        Returns:
            The floor index.

        """
        if floor_index is not None:
            return floor_index
        return int((options or {}).get('floor', 0))

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> None:
        """Add game-specific arguments.

        Args:
            parser: Argument parser.

        """
        parser.add_argument(
            '--floor',
            type=int,
            default=0,
            choices=range(len(ALL_FLOORS)),
            help='Starting floor (0=Boiler Room, 1=Gear Works, 2=Clock Face)',
        )

    @override
    def replay_arguments(self: Self) -> dict[str, Any]:
        """Rebuild this floor with the score and lives carried onto it.

        Returns:
            The constructor arguments the floor was built with (besides options).

        """
        return {
            'floor_index': self.floor_index,
            'player_score': self.starting_player_score,
            'player_lives': self.starting_player_lives,
        }

    @override
    def setup(self: Self) -> None:
        """Set up the floor scene."""
        super().setup()
        self.hud_font = pygame.font.Font(None, 28)
        # Render every sound now so the elevator clank does not render on the slam frame
        self.sounds.prerender()
        # The engine aims the camera at the player each frame (both axes; the bounds above
        # keep it from scrolling sideways) and places every world sprite from it
        self.camera.follow(target=self.player, axes=FollowAxes.BOTH)
        log.info(
            'Clockwork Keep: Floor %d (%s) — %dx%d',
            self.floor_index,
            self.floor_data.name,
            self.floor_data.width,
            self.floor_data.height,
        )

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Master tick: input, physics, collision (the engine then aims the camera).

        Args:
            dt: Delta time in seconds.

        """
        super().dt_tick(dt)

        if self.game_over_triggered:
            return

        self.floor_elapsed_time += dt

        # Check elevator BEFORE begin_frame() clears just_pressed
        self._check_elevator()

        self._process_movement_input()

        world_y_before_tick = self.player.world_y

        # Tick all sprites
        for sprite in self.all_sprites:
            sprite.dt_tick(dt)

        # A gear carries its rider before collision, so the rider is still on it to land
        carried_y = self._ride_moving_gear()

        # The ground check sweeps the fall from where the player was, carried by its gear (the
        # ride is not part of the fall; BUGS.md #205)
        self._player_world_y_before_tick = world_y_before_tick + carried_y

        # Ground collision
        self._resolve_ground_collision()
        self._player_world_y_before_tick = None
        self._play_land_on_touchdown()

        # Pit death
        if (
            not self.player.is_respawning
            and self.player.world_y > self.floor_data.height + PIT_DEATH_THRESHOLD
        ):
            self._player_die()

        # Collectibles (before the victory check, so the cog above the top platform counts)
        self._check_collectibles()

        # Victory: standing on the top floor's highest platform
        if (
            self.victory_platform is not None
            and self.supporting_platform is self.victory_platform
            and not self.player.is_respawning
        ):
            self._win()

    @staticmethod
    def _create_action_map(*, input_mode: str) -> ActionMap:
        """Bind the controls: arrows, SPACE, W, left shift, ESC, Q by position; D-pad, A, Y, X.

        Args:
            input_mode: Gamepad event family ('joystick', 'controller' or 'auto').

        Returns:
            The action map (the golden replays' controls check reads it too).

        """
        actions = ActionMap(input_mode=input_mode)
        # Every control binds a physical key position (a scancode: the same place on every
        # keyboard layout), pause and quit included (ActionMap module docstring)
        actions.bind(
            'move_right',
            scancode=pygame.KSCAN_RIGHT,
            controller_button=pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
        )
        actions.bind(
            'move_left',
            scancode=pygame.KSCAN_LEFT,
            controller_button=pygame.CONTROLLER_BUTTON_DPAD_LEFT,
        )
        actions.bind(
            'jump',
            scancode=pygame.KSCAN_SPACE,
            controller_button=pygame.CONTROLLER_BUTTON_A,
        )
        actions.bind('jump', scancode=pygame.KSCAN_UP)
        actions.bind(
            'interact',
            scancode=pygame.KSCAN_W,
            controller_button=pygame.CONTROLLER_BUTTON_Y,
        )
        actions.bind(
            'run',
            scancode=pygame.KSCAN_LSHIFT,
            controller_button=pygame.CONTROLLER_BUTTON_X,
        )
        actions.bind('pause', scancode=pygame.KSCAN_ESCAPE)
        actions.bind('quit', scancode=pygame.KSCAN_Q)
        return actions

    # --- Movement ---

    def _process_movement_input(self: Self) -> None:
        """Apply held movement actions from ActionMap each frame."""
        self.actions.begin_frame()
        if self.player.is_respawning:
            return
        running = self.actions.is_held('run')
        if self.actions.is_held('move_right'):
            self.player.move_right(running=running)
        elif self.actions.is_held('move_left'):
            self.player.move_left(running=running)
        else:
            self.player.stop_horizontal()

    # --- Collision ---

    def _resolve_ground_collision(self: Self) -> None:
        """Check player against all platforms and snap to ground."""
        # Support comes from the collision rect (hitbox): its left/right edges and its bottom
        # (the visible feet), not the whole drawn image
        player_rect = get_sprite_collision_rect(self.player)
        _, player_offset_y = collision_rect_offset(self.player)
        feet_below_world_y = player_offset_y + player_rect.height
        player_bottom = self.player.world_y + feet_below_world_y
        # Where the feet were before this tick moved them (the swept fall starts there)
        feet_start = self._feet_before_tick(player_bottom=player_bottom)

        self.player.on_ground = False
        self.supporting_platform = None

        for platform in self.platform_sprites:
            plat_top = platform.world_y
            plat_left = platform.world_x
            plat_right = platform.world_x + platform.rect.width

            # Player must be falling onto the platform and within horizontal bounds
            if (
                self._feet_reach_surface(
                    player_bottom=player_bottom, feet_start=feet_start, surface_top=plat_top
                )
                and player_rect.right > plat_left
                and player_rect.left < plat_right
            ):
                self.player.world_y = plat_top - feet_below_world_y
                self.player.velocity_y = 0.0
                self.player.on_ground = True
                self.supporting_platform = platform
                break

        # Also check elevators as ground
        for elevator in self.elevator_sprites:
            elev_top = elevator.world_y
            elev_left = elevator.world_x
            elev_right = elevator.world_x + elevator.rect.width

            if (
                self._feet_reach_surface(
                    player_bottom=player_bottom, feet_start=feet_start, surface_top=elev_top
                )
                and player_rect.right > elev_left
                and player_rect.left < elev_right
            ):
                self.player.world_y = elev_top - feet_below_world_y
                self.player.velocity_y = 0.0
                self.player.on_ground = True
                self.supporting_platform = None
                break

        self.riding_gear = None
        if not self.player.on_ground:
            self._land_on_moving_gear(
                player_rect=player_rect, player_bottom=player_bottom, feet_start=feet_start
            )

    def _feet_before_tick(self: Self, *, player_bottom: float) -> float:
        """Return where the feet were before this tick moved them (no higher than now).

        Outside dt_tick there is no previous position: the feet start where they are.

        Args:
            player_bottom: The world y of the player's feet (its hitbox bottom) now.

        Returns:
            The world y the swept fall starts from.

        """
        if self._player_world_y_before_tick is None:
            return player_bottom
        return min(
            player_bottom,
            player_bottom - (self.player.world_y - self._player_world_y_before_tick),
        )

    def _feet_reach_surface(
        self: Self, *, player_bottom: float, feet_start: float, surface_top: float
    ) -> bool:
        """Whether a falling (or standing) player's feet land on a surface this tick.

        The feet land when they end the tick at or below the surface's top and started it no
        more than GROUND_SNAP_TOLERANCE below it: the fall is swept from where the feet were,
        so a long tick at terminal speed (40 px in a capped 50 ms tick) cannot carry them
        through a platform (BUGS.md #205). Without a previous position (outside dt_tick) the
        feet must end within the tolerance, as before the sweep.

        Args:
            player_bottom: The world y of the player's feet (its hitbox bottom) now.
            feet_start: Where the feet were before this tick (_feet_before_tick).
            surface_top: The world y of the surface's top.

        Returns:
            True if the feet land on the surface.

        """
        if self.player.velocity_y < 0 or player_bottom < surface_top:
            return False
        return feet_start <= surface_top + GROUND_SNAP_TOLERANCE

    def _land_on_moving_gear(
        self: Self, *, player_rect: pygame.Rect, player_bottom: float, feet_start: float
    ) -> None:
        """Stand the player on the moving gear its hitbox lands on, if any.

        A gear supports like a platform, by the gear's collision rect (its visible pixels):
        the player's feet go on its drawn top, so they never float or sink while it moves.

        Args:
            player_rect: The player's collision rect (world coordinates).
            player_bottom: The world y of the player's feet (its hitbox bottom).
            feet_start: Where the feet were before this tick (_feet_before_tick).

        """
        _, player_offset_y = collision_rect_offset(self.player)
        feet_below_world_y = player_offset_y + player_rect.height
        for moving_gear in self.moving_gear_sprites:
            gear_rect = get_sprite_collision_rect(moving_gear)
            if (
                self._feet_reach_surface(
                    player_bottom=player_bottom, feet_start=feet_start, surface_top=gear_rect.top
                )
                and player_rect.right > gear_rect.left
                and player_rect.left < gear_rect.right
            ):
                self.player.world_y = gear_rect.top - feet_below_world_y
                self.player.velocity_y = 0.0
                self.player.on_ground = True
                self.riding_gear = moving_gear
                return

    def _ride_moving_gear(self: Self) -> float:
        """Carry the player by the gear it stands on: as far as the gear moved this tick.

        Runs after every sprite's dt_tick (so the gear has moved) and before ground
        collision, which then finds the player on the gear again. A jump clears on_ground,
        so a player leaving the gear is not carried.

        Returns:
            How far down the gear carried the player (0.0 when it rode no gear).

        """
        if self.riding_gear is None or not self.player.on_ground:
            return 0.0
        self.player.world_x += self.riding_gear.moved_x
        self.player.world_y += self.riding_gear.moved_y
        return self.riding_gear.moved_y

    def _play_land_on_touchdown(self: Self) -> None:
        """Play land on the frame the player touches down.

        Ground collision resets on_ground to False and back every frame, so this compares
        with the previous frame's result. The first result only initializes the edge (the
        transition's off-screen dt_tick must not play it), and respawning resets it (the
        respawn tween sets on_ground directly).
        """
        if self.player.is_respawning:
            self._was_grounded = None
            return
        grounded = self.player.on_ground
        if self._was_grounded is False and grounded:
            self.sounds.play('land')
        self._was_grounded = grounded

    def _try_jump(self: Self) -> None:
        """Jump if standing on something, with its sound."""
        if self.player.on_ground:
            self.player.jump(running=self.actions.is_held('run'))
            self.sounds.play('jump')

    def _check_collectibles(self: Self) -> None:
        """Collect cogs whose collision rect overlaps the player's (via the collision layers)."""
        self.collisions.check_overlap('player', 'cogs', callback=self._on_player_collect_cog)

    def _on_player_collect_cog(self: Self, _player: Tinker, cog: CogCollectible) -> None:
        """Award a cog's points and remove it everywhere."""
        self.player.score += cog.points
        self.sounds.play('cog_pickup')
        cog.kill()
        self.collectible_sprites.remove(cog)
        self.collisions.get_layer('cogs').remove(cog)

    def _check_elevator(self: Self) -> None:
        """Ride the elevator when the player stands on it and presses interact.

        Jump is deliberately not accepted: jumping clears on_ground before this check runs,
        so it could never ride (BUGS.md #24), and jump should always jump.
        """
        if not self.actions.just_pressed('interact'):
            return

        for elevator in self.elevator_sprites:
            elev_top = elevator.world_y
            elev_left = elevator.world_x
            elev_right = elevator.world_x + elevator.rect.width

            # Player must be standing on the elevator
            player_rect = get_sprite_collision_rect(self.player)
            _, player_offset_y = collision_rect_offset(self.player)
            player_bottom = self.player.world_y + player_offset_y + player_rect.height
            on_elevator = (
                self.player.on_ground
                and abs(player_bottom - elev_top) < ELEVATOR_SNAP_TOLERANCE
                and player_rect.right > elev_left
                and player_rect.left < elev_right
            )

            if on_elevator and self.floor_index < len(ALL_FLOORS) - 1:
                self._go_to_next_floor()
                return

    def _draw_timed_clock_background(
        self: Self, surface: pygame.Surface, camera_x: float, camera_y: float
    ) -> None:
        """Draw the floor-3 clock showing this floor's elapsed game time."""
        draw_clock_background(
            surface,
            camera_x,
            camera_y,
            clock_seconds=CLOCK_START_SECONDS + self.floor_elapsed_time,
        )

    def _go_to_next_floor(self: Self) -> None:
        """Ride the elevator to the next floor."""
        next_floor = self.floor_index + 1
        log.info('Elevator activated! Floor %d → %d', self.floor_index, next_floor)

        # The shaft walls take the current floor's platform colours (body and top edge)
        platform_color, top_color, _led_color = _FLOOR_THEMES[self.floor_index]

        next_scene = ClockworkKeepScene(
            floor_index=next_floor,
            player_score=self.player.score,
            player_lives=self.player.lives,
            options=self.options,
        )
        transition = ElevatorTransition(
            duration=ELEVATOR_RIDE_DURATION,
            easing=ELEVATOR_RIDE_EASING,
            wall_color=platform_color,
            wall_accent=top_color,
            player_surface=self.player.image,
            on_update=self._update_elevator_motor,
        )
        self._elevator_peak_velocity = max(
            transition.eased_velocity_at(step / ELEVATOR_SPEED_SAMPLES)
            for step in range(ELEVATOR_SPEED_SAMPLES + 1)
        )
        self._elevator_motor = self._start_elevator_motor(owner=transition)
        transition.add_cue(1.0, self._elevator_arrived)
        self.transition_to(next_scene, transition)

    def _start_elevator_motor(self: Self, *, owner: object) -> LiveVoice | None:
        """Start the motor voice owned by the ride; None (silent ride) if no channel is free.

        Returns:
            The running voice, or None.

        """
        try:
            motor = self.scene_manager.live_audio.create_voice(
                owner=owner,
                waveform=Waveform.SAWTOOTH,
                frequency=ELEVATOR_MOTOR_IDLE_FREQUENCY,
                volume=ELEVATOR_MOTOR_MINIMUM_VOLUME,
                low_pass_cutoff=ELEVATOR_MOTOR_LOW_PASS_CUTOFF,
                tremolo=Tremolo(
                    rate_hz=ELEVATOR_MOTOR_TREMOLO_RATE, depth=ELEVATOR_MOTOR_TREMOLO_DEPTH
                ),
            )
            motor.start()
        except ValueError, AudioUnavailableError:
            log.warning('No live voice or audio available; the elevator rides without its motor')
            return None
        return motor

    def _update_elevator_motor(self: Self, transition: Transition) -> None:
        """Drive motor pitch and volume from the car's speed (the easing's slope).

        Runs from the transition after this scene was cleaned up, so it only touches the
        motor voice, never sprites or the camera.

        Args:
            transition: The running elevator transition.

        """
        # The arrival cue (progress 1.0) fires before on_update on the completing frame and
        # clears the rumble; updating again here would re-start it and never stop.
        if transition.progress >= 1.0:
            return
        speed_fraction = min(
            1.0, transition.eased_velocity_at(transition.progress) / self._elevator_peak_velocity
        )
        # Rumble does not depend on the motor voice: a ride without a free voice still hums
        self.scene_manager.rumble.set_sustained(
            low_frequency=ELEVATOR_ASCENT_RUMBLE_LOW * speed_fraction,
            high_frequency=ELEVATOR_ASCENT_RUMBLE_HIGH * speed_fraction,
        )
        if self._elevator_motor is None:
            return
        self._elevator_motor.frequency = (
            ELEVATOR_MOTOR_IDLE_FREQUENCY
            + (ELEVATOR_MOTOR_PEAK_FREQUENCY - ELEVATOR_MOTOR_IDLE_FREQUENCY) * speed_fraction
        )
        self._elevator_motor.volume = (
            ELEVATOR_MOTOR_MINIMUM_VOLUME
            + (ELEVATOR_MOTOR_MAXIMUM_VOLUME - ELEVATOR_MOTOR_MINIMUM_VOLUME) * speed_fraction
        )

    def _elevator_arrived(self: Self) -> None:
        """The car slams into the floor: stop the motor, clank, shake and rumble.

        Uses only SceneManager-owned services (SCREEN shake), because this scene has been
        cleaned up by the time the ride ends.
        """
        if self._elevator_motor is not None:
            self._elevator_motor.stop_now()
            self._elevator_motor = None
        self.scene_manager.rumble.clear_sustained()
        self.sounds.play('elevator_clank')
        self.shake(ELEVATOR_STOP_BOUNCE, targets=ShakeTarget.SCREEN)
        self.shake(ELEVATOR_STOP_RATTLE, targets=ShakeTarget.SCREEN)

    # --- Victory ---

    def _win(self: Self) -> None:
        """Reaching the top of the Clock Face: save the score and show the victory screen.

        dt_tick returns early once game_over_triggered is set, so this runs once.
        """
        self.game_over_triggered = True
        log.info('Victory! Score: %d', self.player.score)
        # The floor (and its camera) stand still from here on: stop following
        self.camera.follow(target=None)
        self.sounds.play('elevator_clank')
        self._save_high_score()
        # A shake still running would carry into the fade; end it first (as at game over)
        self.scene_manager.screen_shake.clear()
        victory = ClockworkKeepVictoryScene(
            final_score=self.player.score,
            high_scores=self._load_high_scores(),
            options=self.options,
        )
        self.transition_to(victory, FadeTransition(duration=1.0))

    # --- Death / Respawn ---

    def _player_die(self: Self) -> None:
        """Handle player death."""
        if self.game_over_triggered:
            return

        self.player.lives -= 1
        log.info('Player died! Lives: %d', self.player.lives)

        if self.player.lives <= 0:
            self.game_over_triggered = True
            # The floor (and its camera) stand still from here on: stop following
            self.camera.follow(target=None)
            self.sounds.play('game_over')
            self._save_high_score()
            # Spec revision 3: a shake still running would carry into the fade; end it first.
            self.scene_manager.screen_shake.clear()
            high_scores = self._load_high_scores()
            game_over = GameOverScene(
                final_score=self.player.score,
                high_scores=high_scores,
                options=self.options,
            )
            self.transition_to(game_over, FadeTransition(duration=1.0))
        else:
            self.sounds.play('death')
            self._respawn_player()

    def _respawn_player(self: Self) -> None:
        """Respawn with fade animation."""
        self.player.is_respawning = True
        self.player.velocity_x = 0.0
        self.player.velocity_y = 0.0
        self.player.stop_horizontal()

        spawn_x = float(self.floor_data.spawn_x)
        spawn_y = float(self.floor_data.spawn_y)

        def _reposition_and_fade_in() -> None:
            self.player.world_x = spawn_x
            self.player.world_y = spawn_y
            self.player.on_ground = True
            # The spawn point stands on no gear: the gear faded out on carries no one
            self.riding_gear = None
            self.player.is_respawning = False
            self.tweens.tween(
                target=self.player,
                property_name='alpha',
                end_value=255.0,
                duration=0.3,
                easing='ease_out_quad',
            )

        self.tweens.tween(
            target=self.player,
            property_name='alpha',
            end_value=0.0,
            duration=0.2,
            easing='ease_in_quad',
            on_complete=_reposition_and_fade_in,
        )

    # --- Save / Load ---

    def _save_high_score(self: Self) -> None:
        """Save score and highest floor to persistent storage."""
        max_entries = 10
        try:
            existing = self.saves.load('high_scores')
            scores: list[dict[str, int]] = existing.get('scores', [])
        except SaveNotFoundError:
            scores = []

        scores.append({
            'score': self.player.score,
            'floor': self.floor_index,
        })
        scores.sort(key=lambda entry: entry.get('score', 0), reverse=True)
        scores = scores[:max_entries]
        self.saves.save('high_scores', {'scores': scores})

    def _load_high_scores(self: Self) -> list[dict[str, int]]:
        """Load high scores from persistent storage.

        Returns:
            List of high score dicts.

        """
        try:
            data = self.saves.load('high_scores')
            return data.get('scores', [])
        except SaveNotFoundError:
            return []

    # --- Input handlers ---

    @override
    def on_window_focus_lost_event(self: Self, event: WindowEvent) -> None:
        """Auto-pause when the window loses focus (Cmd-Tab, etc.).

        Args:
            event: The focus lost event.

        """
        super().on_window_focus_lost_event(event)
        if not self.game_over_triggered:
            self.next_scene = PauseScene(options=self.options)

    @override
    def on_key_down_event(self: Self, event: KeyEvent) -> None:
        """Handle key presses.

        Args:
            event: The key down event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action == 'jump':
            self._try_jump()
        elif action == 'pause':
            self.next_scene = PauseScene(options=self.options)
        elif action == 'quit':
            # A QUIT event ends the run (next_scene = None does not: the scene manager reads it
            # as no switch pending)
            self.scene_manager.quit()
        elif action is None:
            super().on_key_down_event(event)

    @override
    def on_key_up_event(self: Self, event: KeyEvent) -> None:
        """Handle key releases.

        Args:
            event: The key up event.

        """
        self.actions.handle_event(event)

    @override
    def on_joy_button_down_event(self: Self, event: JoyButtonEvent) -> None:
        """Handle joystick button presses.

        Args:
            event: The joystick button down event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action == 'jump':
            self._try_jump()

    @override
    def on_joy_button_up_event(self: Self, event: JoyButtonEvent) -> None:
        """Handle joystick button releases.

        Args:
            event: The joystick button up event.

        """
        self.actions.handle_event(event)

    @override
    def on_joy_axis_motion_event(self: Self, event: JoyAxisEvent) -> None:
        """Handle joystick axis motion.

        Args:
            event: The joystick axis motion event.

        """
        self.actions.handle_event(event)

    @override
    def on_controller_button_down_event(self: Self, event: ControllerButtonEvent) -> None:
        """Handle controller button presses.

        Args:
            event: The controller button down event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action == 'jump':
            self._try_jump()

    @override
    def on_controller_button_up_event(self: Self, event: ControllerButtonEvent) -> None:
        """Handle controller button releases.

        Args:
            event: The controller button up event.

        """
        self.actions.handle_event(event)

    # --- Rendering ---

    @override
    def render(self: Self, screen: pygame.Surface) -> None:
        """Render the floor.

        Args:
            screen: Display surface.

        """
        # Set in __init__ (the setter takes no None); the getter is typed for before Scene.__init__
        assert self.background_color is not None
        screen.fill(self.background_color)
        self.all_sprites.clear(screen, self.background)
        self.all_sprites.draw(screen)
        self._draw_hud(screen)
        self.rects = None  # Full screen update

    def _draw_hud(self: Self, screen: pygame.Surface) -> None:
        """Draw score, lives, and floor indicator.

        Args:
            screen: Display surface.

        """
        if self.hud_font is None:
            return

        antialias = True
        score_text = f'Score: {self.player.score}'
        lives_text = f'Lives: {self.player.lives}'
        floor_text = f'Floor: {self.floor_data.name}'

        # Score (top left)
        shadow = self.hud_font.render(score_text, antialias, HUD_SHADOW_COLOR)
        screen.blit(shadow, (11, 11))
        text = self.hud_font.render(score_text, antialias, HUD_TEXT_COLOR)
        screen.blit(text, (10, 10))

        # Lives (top right)
        shadow = self.hud_font.render(lives_text, antialias, HUD_SHADOW_COLOR)
        screen.blit(shadow, (self.screen_width - 109, 11))
        text = self.hud_font.render(lives_text, antialias, HUD_TEXT_COLOR)
        screen.blit(text, (self.screen_width - 110, 10))

        # Floor name (top center)
        shadow = self.hud_font.render(floor_text, antialias, HUD_SHADOW_COLOR)
        floor_x = (self.screen_width - shadow.get_width()) // 2
        screen.blit(shadow, (floor_x + 1, 11))
        text = self.hud_font.render(floor_text, antialias, HUD_TEXT_COLOR)
        screen.blit(text, (floor_x, 10))


class ClockworkKeepVictoryScene(GameOverScene):
    """The end of the climb: GameOverScene's score and high scores under a VICTORY! title.

    Space starts a new climb and Esc quits, as on the game-over screen.
    """

    VICTORY_TITLE_COLOR = (255, 200, 50)  # The Clock Face's brass LED

    @override
    def setup(self: Self) -> None:
        """Lay out the game-over screen, then replace its GAME OVER title with VICTORY!."""
        super().setup()
        assert self.text_sprite is not None, 'GameOverScene.setup() makes the title'
        title_center_x, title_center_y = self.text_sprite.rect.center
        self.text_sprite.kill()
        self.text_sprite = TextSprite(
            'VICTORY!',
            (round(title_center_x), round(title_center_y)),
            color=self.VICTORY_TITLE_COLOR,
            font_size=48,
        )
        self.all_sprites.add(self.text_sprite)


def main() -> None:
    """Run Clockwork Keep."""
    GameEngine(game=ClockworkKeepScene).start()


if __name__ == '__main__':
    main()
