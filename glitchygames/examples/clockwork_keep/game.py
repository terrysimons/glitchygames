"""Main game scene for Clockwork Keep — a steampunk tower climb."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.audio.exceptions import AudioUnavailableError
from glitchygames.audio.recipes import SoundBank, Tremolo
from glitchygames.audio.synth import Waveform
from glitchygames.camera import Camera2D
from glitchygames.collision.layers import get_sprite_collision_rect
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
from glitchygames.examples.clockwork_keep.terrain import Elevator, Platform
from glitchygames.input import ActionMap
from glitchygames.scenes import Scene
from glitchygames.scenes.builtin_scenes.game_over_scene import GameOverScene
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.sprites import Sprite
from glitchygames.state import SaveManager, SaveNotFoundError
from glitchygames.transitions import ElevatorTransition, FadeTransition

if TYPE_CHECKING:
    import argparse

    from glitchygames.audio.live import LiveVoice
    from glitchygames.events.base import HashableEvent
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

    def apply_camera(self, camera: Camera2D) -> None:
        """Update screen position from camera.

        Args:
            camera: The camera for world-to-screen transform.

        """
        screen_x, screen_y = camera.apply(self.world_x, self.world_y)
        self.rect.x = screen_x
        self.rect.y = screen_y


class ClockworkKeepScene(Scene):
    """One floor of the clockwork tower.

    Each floor is a separate Scene instance. Elevators trigger
    scene transitions to the next floor.
    """

    NAME = 'Clockwork Keep'
    VERSION = '1.0'

    def __init__(
        self: Self,
        floor_index: int = 0,
        player_score: int = 0,
        player_lives: int = 3,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize the floor scene.

        Args:
            floor_index: Which floor (0=Boiler Room, 1=Gear Works, 2=Clock Face).
            player_score: Score carried from previous floor.
            player_lives: Lives carried from previous floor.
            options: Command-line options.
            groups: Sprite group.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(options=options, groups=groups)

        self.floor_index = floor_index
        self.floor_data: FloorData = ALL_FLOORS[floor_index]
        # Game time on this floor (capped dt, frozen after game over); drives the floor-3 clock
        self.floor_elapsed_time: float = 0.0

        # Theme colors
        platform_color, top_color, self.led_color = _FLOOR_THEMES[floor_index]

        # Background
        bg_color = [
            (40, 25, 15),  # Boiler Room
            (35, 35, 40),  # Gear Works
            (15, 15, 35),  # Clock Face
        ][floor_index]
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
        bg_func = (
            self._draw_timed_clock_background
            if _FLOOR_BACKGROUNDS[floor_index] is draw_clock_background
            else _FLOOR_BACKGROUNDS[floor_index]
        )
        self.camera.add_background_layer(
            scroll_factor=PARALLAX_FAR,
            draw_function=bg_func,
            layer_depth=LAYER_FAR_BACKGROUND,
            groups=self.all_sprites,
        )

        # Build terrain
        self.platform_sprites: list[Platform] = []
        self.elevator_sprites: list[Elevator] = []
        self.collectible_sprites: list[CogCollectible] = []

        for platform_x, platform_y, platform_width in self.floor_data.platforms:
            platform = Platform(
                world_x=float(platform_x),
                world_y=float(platform_y),
                width=platform_width,
                platform_color=platform_color,
                top_color=top_color,
                groups=self.all_sprites,
            )
            self.platform_sprites.append(platform)

        for elevator_x, elevator_y in self.floor_data.elevators:
            elevator = Elevator(
                world_x=float(elevator_x),
                world_y=float(elevator_y),
                groups=self.all_sprites,
            )
            self.elevator_sprites.append(elevator)

        for cog_x, cog_y, cog_type in self.floor_data.collectibles:
            cog = CogCollectible(
                world_x=float(cog_x),
                world_y=float(cog_y),
                cog_type=cog_type,
                groups=self.all_sprites,
            )
            self.collectible_sprites.append(cog)

        # Player
        self.player = Tinker(
            world_x=float(self.floor_data.spawn_x),
            world_y=float(self.floor_data.spawn_y),
            groups=self.all_sprites,
        )
        self.player.score = player_score
        self.player.lives = player_lives
        self.player.floor = floor_index

        # Game state
        self.game_over_triggered: bool = False

        # Sound
        self.sounds = SoundBank(ALL_RECIPES)
        self._was_grounded: bool | None = None  # Set from the first real collision result
        self._elevator_motor: LiveVoice | None = None
        self._elevator_peak_velocity = 1.0

        # Persistence
        self.saves = SaveManager(app_name='clockwork-keep')

        # Input
        input_mode = self.options.get('input_mode', 'joystick')
        self.actions = ActionMap(input_mode=input_mode)
        self.actions.bind(
            'move_right',
            keyboard=pygame.K_RIGHT,
            controller_button=pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
        )
        self.actions.bind(
            'move_left',
            keyboard=pygame.K_LEFT,
            controller_button=pygame.CONTROLLER_BUTTON_DPAD_LEFT,
        )
        self.actions.bind(
            'jump',
            keyboard=pygame.K_SPACE,
            controller_button=pygame.CONTROLLER_BUTTON_A,
        )
        self.actions.bind('jump', keyboard=pygame.K_UP)
        self.actions.bind(
            'interact',
            keyboard=pygame.K_w,
            controller_button=pygame.CONTROLLER_BUTTON_Y,
        )
        self.actions.bind(
            'run',
            keyboard=pygame.K_LSHIFT,
            controller_button=pygame.CONTROLLER_BUTTON_X,
        )
        self.actions.bind('pause', keyboard=pygame.K_ESCAPE)
        self.actions.bind('quit', keyboard=pygame.K_q)

        # HUD
        self.hud_font: pygame.font.Font | None = None

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
            help='Starting floor (0=Boiler Room, 1=Gear Works, 2=Clock Face)',
        )

    @override
    def setup(self: Self) -> None:
        """Set up the floor scene."""
        super().setup()
        self.hud_font = pygame.font.Font(None, 28)
        # Render every sound now so the elevator clank does not render on the slam frame
        self.sounds.prerender()
        log.info(
            'Clockwork Keep: Floor %d (%s) — %dx%d',
            self.floor_index,
            self.floor_data.name,
            self.floor_data.width,
            self.floor_data.height,
        )

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Master tick: input, physics, collision, camera.

        Args:
            dt: Delta time in seconds.

        """
        super().dt_tick(dt)

        if self.game_over_triggered:
            return

        # Cap dt to prevent physics tunneling after focus loss (Cmd-Tab, etc.)
        max_dt = 0.05  # 50ms = 20fps minimum
        dt = min(dt, max_dt)

        self.floor_elapsed_time += dt

        # Check elevator BEFORE begin_frame() clears just_pressed
        self._check_elevator()

        self._process_movement_input()

        # Tick all sprites
        for sprite in self.all_sprites:
            sprite.dt_tick(dt)

        # Ground collision
        self._resolve_ground_collision()
        self._play_land_on_touchdown()

        # Pit death
        if (
            not self.player.is_respawning
            and self.player.world_y > self.floor_data.height + PIT_DEATH_THRESHOLD
        ):
            self._player_die()

        # Collectibles
        self._check_collectibles()

        # Camera follows player (both axes)
        self.camera.update(
            target_x=self.player.world_x,
            target_y=self.player.world_y,
            dt=dt,
        )

        # Apply camera to all world-space sprites
        self.apply_camera_to_sprites()

    @override
    def apply_camera_to_sprites(self: Self) -> None:
        """Position every world-space sprite from the camera."""
        camera = self.camera
        self.player.apply_camera(camera)
        for platform in self.platform_sprites:
            platform.apply_camera(camera)
        for elevator in self.elevator_sprites:
            elevator.apply_camera(camera)
        for cog in self.collectible_sprites:
            cog.apply_camera(camera)

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
        player_bottom = self.player.world_y + self.player.rect.height
        # Horizontal support comes from the collision rect (hitbox), not the drawn width
        player_rect = get_sprite_collision_rect(self.player)

        self.player.on_ground = False

        for platform in self.platform_sprites:
            plat_top = platform.world_y
            plat_left = platform.world_x
            plat_right = platform.world_x + platform.rect.width

            # Player must be above or at platform level and within horizontal bounds
            if (
                self.player.velocity_y >= 0
                and player_bottom >= plat_top
                and player_bottom <= plat_top + 20
                and player_rect.right > plat_left
                and player_rect.left < plat_right
            ):
                self.player.world_y = plat_top - self.player.rect.height
                self.player.velocity_y = 0.0
                self.player.on_ground = True
                break

        # Also check elevators as ground
        for elevator in self.elevator_sprites:
            elev_top = elevator.world_y
            elev_left = elevator.world_x
            elev_right = elevator.world_x + elevator.rect.width

            if (
                self.player.velocity_y >= 0
                and player_bottom >= elev_top
                and player_bottom <= elev_top + 20
                and player_rect.right > elev_left
                and player_rect.left < elev_right
            ):
                self.player.world_y = elev_top - self.player.rect.height
                self.player.velocity_y = 0.0
                self.player.on_ground = True
                break

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
        """Check player against collectibles."""
        player_rect = pygame.Rect(
            round(self.player.world_x),
            round(self.player.world_y),
            self.player.rect.width,
            self.player.rect.height,
        )
        for cog in list(self.collectible_sprites):
            cog_rect = pygame.Rect(
                round(cog.world_x),
                round(cog.world_y),
                COG_SIZE,
                COG_SIZE,
            )
            if player_rect.colliderect(cog_rect):
                self.player.score += cog.points
                self.sounds.play('cog_pickup')
                cog.kill()
                self.collectible_sprites.remove(cog)

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
            player_bottom = self.player.world_y + self.player.rect.height
            player_rect = get_sprite_collision_rect(self.player)
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

        # Use the current floor's wall colors for the shaft
        _platform_color, _top_color, _led_color = _FLOOR_THEMES[self.floor_index]

        next_scene = ClockworkKeepScene(
            floor_index=next_floor,
            player_score=self.player.score,
            player_lives=self.player.lives,
            options=self.options,
        )
        transition = ElevatorTransition(
            duration=ELEVATOR_RIDE_DURATION,
            easing=ELEVATOR_RIDE_EASING,
            wall_color=_FLOOR_THEMES[self.floor_index][0],
            wall_accent=_FLOOR_THEMES[self.floor_index][1],
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

    # --- Death / Respawn ---

    def _player_die(self: Self) -> None:
        """Handle player death."""
        if self.game_over_triggered:
            return

        self.player.lives -= 1
        log.info('Player died! Lives: %d', self.player.lives)

        if self.player.lives <= 0:
            self.game_over_triggered = True
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
    def on_window_focus_lost_event(self: Self, event: HashableEvent) -> None:
        """Auto-pause when the window loses focus (Cmd-Tab, etc.).

        Args:
            event: The focus lost event.

        """
        super().on_window_focus_lost_event(event)
        if not self.game_over_triggered:
            self.next_scene = PauseScene(options=self.options)

    @override
    def on_key_down_event(self: Self, event: HashableEvent) -> None:
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
            self.next_scene = None
        elif action is None:
            super().on_key_down_event(event)

    @override
    def on_key_up_event(self: Self, event: HashableEvent) -> None:
        """Handle key releases.

        Args:
            event: The key up event.

        """
        self.actions.handle_event(event)

    @override
    def on_joy_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button presses.

        Args:
            event: The joystick button down event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action == 'jump':
            self._try_jump()

    @override
    def on_joy_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button releases.

        Args:
            event: The joystick button up event.

        """
        self.actions.handle_event(event)

    @override
    def on_joy_axis_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick axis motion.

        Args:
            event: The joystick axis motion event.

        """
        self.actions.handle_event(event)

    @override
    def on_controller_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle controller button presses.

        Args:
            event: The controller button down event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action == 'jump':
            self._try_jump()

    @override
    def on_controller_button_up_event(self: Self, event: HashableEvent) -> None:
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
        if self.background_color is not None:
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


def main() -> None:
    """Run Clockwork Keep."""
    GameEngine(game=ClockworkKeepScene).start()


if __name__ == '__main__':
    main()
