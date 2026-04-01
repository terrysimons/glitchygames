"""Main game scene for Brave Adventurer - a Pitfall clone set in ancient Egypt."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.audio import VoiceAssistant
from glitchygames.camera import Camera2D
from glitchygames.engine import GameEngine
from glitchygames.examples.brave_adventurer.constants import (
    CAMERA_LEAD,
    COLLECTIBLE_SCORE_BONUS,
    DISTANCE_SCORE_DIVISOR,
    GROUND_Y,
    HUD_SHADOW_COLOR,
    HUD_TEXT_COLOR,
    LAYER_FAR_BACKGROUND,
    LAYER_MID_BACKGROUND,
    LAYER_NEAR_BACKGROUND,
    LAYER_SKY,
    PARALLAX_FAR,
    PARALLAX_MID,
    PARALLAX_NEAR,
    PARALLAX_SKY,
    PIT_DEATH_THRESHOLD,
    PIT_EDGE_COLOR,
    PIT_FLOOR_COLOR,
    PIT_WALL_COLOR,
    PIT_WALL_SHADOW,
    PLAYER_HEIGHT,
    PLAYER_WIDTH,
    RESPAWN_OFFSET,
    SCARAB_HEIGHT,
    SCARAB_WIDTH,
    SCREEN_HEIGHT,
    SKY_COLOR,
    STONE_WALL_WIDTH,
)
from glitchygames.examples.brave_adventurer.drawing import (
    draw_dunes_and_oasis,
    draw_near_ground_details,
    draw_pyramids,
    draw_sky,
)
from glitchygames.examples.brave_adventurer.levels import LEVEL_1, LevelManager
from glitchygames.examples.brave_adventurer.player import Player
from glitchygames.examples.brave_adventurer.sounds import GameSounds
from glitchygames.input import ActionMap
from glitchygames.scenes import Scene
from glitchygames.scenes.builtin_scenes.game_over_scene import GameOverScene
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.state import SaveManager, SaveNotFoundError

if TYPE_CHECKING:
    import argparse

    from glitchygames.events.base import HashableEvent

log = logging.getLogger('game')

# DualSense mic mute button indices differ between APIs:
# SDL Game Controller API reports button 15
# Raw joystick API reports button 16
MIC_BUTTON_CONTROLLER = 15
MIC_BUTTON_JOYSTICK = 16


class BraveAdventurerScene(Scene):
    """Main gameplay scene for Brave Adventurer.

    Orchestrates the player, camera, terrain, enemies, parallax backgrounds,
    and HUD. The game is a Pitfall-style side-scrolling platformer set in
    ancient Egypt.
    """

    NAME = 'Brave Adventurer'
    VERSION = '1.0'

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize the game scene.

        Args:
            options: Command-line options dict from GameEngine.
            groups: Sprite group (created if not provided).

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(options=options, groups=groups)

        # Set background to sky color
        self.background_color = SKY_COLOR

        # Camera with parallax background layers
        self.camera = Camera2D(
            screen_width=self.screen_width,
            screen_height=self.screen_height,
            lead_x=CAMERA_LEAD,
        )
        self.camera.set_bounds(min_x=0.0)

        self.camera.add_background_layer(
            scroll_factor=PARALLAX_SKY,
            draw_function=draw_sky,
            layer_depth=LAYER_SKY,
            groups=self.all_sprites,
        )
        self.camera.add_background_layer(
            scroll_factor=PARALLAX_FAR,
            draw_function=draw_pyramids,
            layer_depth=LAYER_FAR_BACKGROUND,
            groups=self.all_sprites,
        )
        self.camera.add_background_layer(
            scroll_factor=PARALLAX_MID,
            draw_function=draw_dunes_and_oasis,
            layer_depth=LAYER_MID_BACKGROUND,
            groups=self.all_sprites,
        )
        self.camera.add_background_layer(
            scroll_factor=PARALLAX_NEAR,
            draw_function=draw_near_ground_details,
            layer_depth=LAYER_NEAR_BACKGROUND,
            groups=self.all_sprites,
        )

        # Build the level (creates ground, walls, enemies, collectibles)
        self.level_manager = LevelManager(
            level_data=LEVEL_1,
            groups=self.all_sprites,
        )
        self.ground_sprites = self.level_manager.ground_sprites
        self.wall_sprites = self.level_manager.wall_sprites
        self.enemy_sprites = self.level_manager.enemy_sprites
        self.collectible_sprites = self.level_manager.collectible_sprites

        # Player (on top of sprites so it renders above terrain)
        self.player = Player(
            world_x=100.0,
            world_y=GROUND_Y - PLAYER_HEIGHT,
            groups=self.all_sprites,
        )

        # Collision layers
        player_collision_layer = self.collisions.add_layer('player')
        enemy_collision_layer = self.collisions.add_layer('enemies')
        collectible_collision_layer = self.collisions.add_layer('collectibles')
        player_collision_layer.add(self.player)
        for enemy in self.enemy_sprites:
            enemy_collision_layer.add(enemy)
        for collectible in self.collectible_sprites:
            collectible_collision_layer.add(collectible)

        # Game state
        self.game_over_triggered: bool = False

        # Persistence
        self.saves = SaveManager(app_name='brave-adventurer')

        # Sound effects (generated from waveforms, initialized in setup)
        self.sounds = GameSounds()

        # Track whether player was airborne last frame (for land sound)
        self._was_airborne: bool = False

        # HUD font
        self.hud_font: pygame.font.Font | None = None

        # Input action mapping (unifies keyboard + controller)
        self.actions = ActionMap(input_mode=self.options.get('input_mode', 'joystick'))
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
        self.actions.bind('pause', keyboard=pygame.K_ESCAPE)
        self.actions.bind('quit', keyboard=pygame.K_q)

        # Mic mute button — bind both APIs since button indices differ
        self.actions.bind(
            'mic_toggle',
            controller_button=MIC_BUTTON_CONTROLLER,
            joystick_button=MIC_BUTTON_JOYSTICK,
        )

        # Voice assistant (auto-discovers controller mic/speaker)
        # Voice assistant auto-discovers controller mic/speaker via miniaudio
        self.voice_assistant: VoiceAssistant | None = VoiceAssistant.discover()

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> None:
        """Add game-specific command-line arguments.

        Args:
            parser: The argument parser to add arguments to.

        """
        parser.add_argument(
            '-v',
            '--version',
            action='store_true',
            help='print the game version and exit',
        )

    @override
    def setup(self: Self) -> None:
        """Set up the game scene."""
        super().setup()
        if self.target_fps == 0:
            self.target_fps = 60
        self.hud_font = pygame.font.Font(None, 28)
        self.sounds.initialize()
        log.info('Brave Adventurer setup complete')

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Master tick: physics, collision, camera, scoring.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        super().dt_tick(dt)

        if self.game_over_triggered:
            return

        # 0. Process input and voice assistant
        self._process_movement_input()
        self._update_voice_assistant()

        # 1. Track airborne state before physics (for landing sound)
        was_airborne_before = not self.player.on_ground

        # 2. Tick all sprites (player physics, enemy AI, collectible bobbing)
        for sprite in self.all_sprites:
            sprite.dt_tick(dt)

        # 3. Ground collision
        self._resolve_player_ground_collision()

        # 4. Landing sound (transitioned from airborne to grounded)
        if was_airborne_before and self.player.on_ground:
            self.sounds.play_land()

        # 5. Wall collision
        self._resolve_player_wall_collision()

        # 5b. Enemy terrain collision (scarabs follow ground/walls)
        self._resolve_enemy_terrain_collisions()

        # 6. Pit death check (skip during respawn animation)
        if (
            not self.player.is_respawning
            and self.player.world_y > self.screen_height + PIT_DEATH_THRESHOLD
        ):
            self._player_die()

        # 5. Enemy collision (skip during respawn invincibility)
        if not self.player.is_respawning:
            self._check_enemy_collisions()

        # 6. Collectible pickup
        self._check_collectible_collisions()

        # 7. Update camera to follow player
        self.camera.update(
            target_x=self.player.world_x,
            target_y=0.0,
            dt=self.dt,
        )

        # 8. Apply camera transform to all world-space sprites
        self.player.apply_camera(self.camera)
        for ground_segment in self.ground_sprites:
            ground_segment.apply_camera(self.camera)
        for wall in self.wall_sprites:
            wall.apply_camera(self.camera)
        for enemy in self.enemy_sprites:
            enemy.apply_camera(self.camera)
        for collectible in self.collectible_sprites:
            collectible.apply_camera(self.camera)

        # 9. Update distance score (parallax updated automatically by Camera2D)
        self.player.max_distance = max(self.player.max_distance, self.player.world_x)
        self.player.score = round(self.player.max_distance / DISTANCE_SCORE_DIVISOR)

    def _get_trailing_foot_x(self: Self, body_x: float, body_width: int, velocity_x: float) -> int:
        """Get the X coordinate of the trailing foot for ground checks.

        Uses the back foot so the player doesn't fall until their
        trailing edge actually leaves the ground.

        Returns:
            The X pixel coordinate of the trailing foot.

        """
        left = round(body_x)
        if velocity_x > 0:
            return left
        if velocity_x < 0:
            return left + body_width
        return left + body_width // 2

    def _resolve_player_ground_collision(self: Self) -> None:
        """Check if the player lands on ground and snap to the surface."""
        self.player.on_ground = False

        trailing_foot_x = self._get_trailing_foot_x(
            body_x=self.player.world_x,
            body_width=PLAYER_WIDTH,
            velocity_x=self.player.velocity_x,
        )
        player_bottom = round(self.player.world_y) + PLAYER_HEIGHT

        if self.ground_sprites:
            for ground_segment in self.ground_sprites:
                segment_left = round(ground_segment.world_x)
                segment_right = segment_left + ground_segment.segment_width

                # Player's trailing foot must still be over this segment
                feet_over_segment = (
                    trailing_foot_x >= segment_left and trailing_foot_x < segment_right
                )
                feet_on_surface = player_bottom >= GROUND_Y

                if feet_over_segment and feet_on_surface and self.player.velocity_y >= 0:
                    self.player.world_y = GROUND_Y - PLAYER_HEIGHT
                    self.player.velocity_y = 0.0
                    self.player.on_ground = True
                    break
        elif player_bottom >= GROUND_Y and self.player.velocity_y >= 0:
            # Fallback: infinite flat ground when no segments defined
            self.player.world_y = GROUND_Y - PLAYER_HEIGHT
            self.player.velocity_y = 0.0
            self.player.on_ground = True

        # If the player is in a pit (below ground, not on ground), the edges
        # of adjacent ground segments act as walls to prevent climbing out.
        if not self.player.on_ground and round(self.player.world_y) + PLAYER_HEIGHT > GROUND_Y:
            player_left = round(self.player.world_x)
            player_right = player_left + PLAYER_WIDTH

            for ground_segment in self.ground_sprites:
                segment_left = round(ground_segment.world_x)
                segment_right = segment_left + ground_segment.segment_width

                # Moving right into the left edge of a segment
                if (
                    self.player.velocity_x > 0
                    and player_right > segment_left
                    and player_left < segment_left
                ):
                    self.player.world_x = segment_left - PLAYER_WIDTH
                    break

                # Moving left into the right edge of a segment
                if (
                    self.player.velocity_x < 0
                    and player_left < segment_right
                    and player_right > segment_right
                ):
                    self.player.world_x = float(segment_right)
                    break

    def _resolve_player_wall_collision(self: Self) -> None:
        """Check if the player collides with stone walls.

        Handles two cases:
        1. Landing on top of a wall (treated like ground)
        2. Walking into the side of a wall (horizontal push-back)

        The "on top" check must run first, otherwise a player standing
        on a wall gets pushed sideways when they try to walk.
        """
        player_left = round(self.player.world_x)
        player_right = player_left + PLAYER_WIDTH
        player_top = round(self.player.world_y)
        player_bottom = player_top + PLAYER_HEIGHT

        for wall in self.wall_sprites:
            wall_left = round(wall.world_x)
            wall_right = wall_left + STONE_WALL_WIDTH
            wall_top = round(wall.world_y)
            wall_bottom = wall_top + wall.wall_height

            # Check horizontal overlap (needed for both top and side collisions)
            horizontally_overlapping = player_right > wall_left and player_left < wall_right

            if not horizontally_overlapping:
                continue

            # Case 1: Landing on top of the wall.
            # Feet must be within a small margin of the wall surface to count
            # as "on top". Prevents walking through short walls when the player
            # is taller than the wall.
            landing_tolerance = 16
            standing_on_top = (
                player_bottom >= wall_top
                and player_bottom <= wall_top + landing_tolerance
                and player_top < wall_top
                and self.player.velocity_y >= 0
            )

            if standing_on_top:
                self.player.world_y = wall_top - PLAYER_HEIGHT
                self.player.velocity_y = 0.0
                self.player.on_ground = True
                continue

            # Case 2: Side collision (walking into the wall).
            # Only applies when the player overlaps vertically with the wall body.
            vertically_overlapping = player_bottom > wall_top and player_top < wall_bottom

            if vertically_overlapping:
                if self.player.velocity_x > 0:
                    self.player.world_x = wall.world_x - PLAYER_WIDTH
                elif self.player.velocity_x < 0:
                    self.player.world_x = wall.world_x + STONE_WALL_WIDTH

    def _resolve_enemy_terrain_collisions(self: Self) -> None:
        """Resolve enemy-terrain collisions so scarabs follow the ground.

        Scarabs land on ground segments (including pit floors) and are
        blocked by stone walls.
        """
        from glitchygames.examples.brave_adventurer.enemies import Scarab

        for enemy in self.enemy_sprites:
            if not isinstance(enemy, Scarab):
                continue

            scarab_bottom = enemy.world_y + SCARAB_HEIGHT

            # Ground collision: land on the nearest ground segment
            landed = False
            if self.ground_sprites:
                scarab_center_x = round(enemy.world_x) + SCARAB_WIDTH // 2
                for ground_segment in self.ground_sprites:
                    segment_left = round(ground_segment.world_x)
                    segment_right = segment_left + ground_segment.segment_width

                    over_segment = (
                        scarab_center_x >= segment_left and scarab_center_x < segment_right
                    )
                    if over_segment and scarab_bottom >= GROUND_Y and enemy.velocity_y >= 0:
                        enemy.world_y = GROUND_Y - SCARAB_HEIGHT
                        enemy.velocity_y = 0.0
                        enemy.on_ground = True
                        landed = True
                        break

            # Pit floor: if scarab fell below ground level, land on pit floor
            pit_floor_y = self.screen_height - SCARAB_HEIGHT
            if not landed and scarab_bottom >= self.screen_height:
                enemy.world_y = float(pit_floor_y)
                enemy.velocity_y = 0.0
                enemy.on_ground = True

            # Wall collision: reverse direction when hitting a wall
            for wall in self.wall_sprites:
                wall_left = round(wall.world_x)
                wall_right = wall_left + STONE_WALL_WIDTH
                scarab_left = round(enemy.world_x)
                scarab_right = scarab_left + SCARAB_WIDTH

                if scarab_right > wall_left and scarab_left < wall_right:
                    # Scarab is overlapping wall -- reverse direction
                    if enemy.roll_speed < 0:
                        enemy.world_x = float(wall_right)
                    else:
                        enemy.world_x = float(wall_left - SCARAB_WIDTH)
                    enemy.roll_speed = -enemy.roll_speed

    def _check_enemy_collisions(self: Self) -> None:
        """Check if the player touches any enemy (results in death).

        Uses the collision manager for hitbox-aware detection.
        """
        self.collisions.check_overlap(
            'player',
            'enemies',
            callback=self._on_player_enemy_collision,
        )

    def _on_player_enemy_collision(self: Self, _player: Any, _enemy: Any) -> None:
        """Handle player-enemy collision by triggering death."""
        self._player_die()

    def _check_collectible_collisions(self: Self) -> None:
        """Check if the player picks up any gold scarabs.

        Uses the collision manager for hitbox-aware detection.
        """
        self.collisions.check_overlap(
            'player',
            'collectibles',
            callback=self._on_player_collect,
        )

    def _on_player_collect(self: Self, _player: Any, collectible: Any) -> None:
        """Handle player-collectible collision by awarding points."""
        self.player.score += COLLECTIBLE_SCORE_BONUS
        self.sounds.play_collect()
        collectible.kill()
        self.collectible_sprites.remove(collectible)
        self.collisions.get_layer('collectibles').remove(collectible)

    def _player_die(self: Self) -> None:
        """Handle player death: lose a life or trigger game over."""
        if self.game_over_triggered:
            return

        self.player.lives -= 1
        log.info('Player died! Lives remaining: %d', self.player.lives)

        if self.player.lives <= 0:
            self.game_over_triggered = True
            self.sounds.play_game_over()
            high_scores = self._save_high_score()
            game_over_scene = GameOverScene(
                final_score=self.player.score,
                high_scores=high_scores,
                options=self.options,
            )
            self.next_scene = game_over_scene
        else:
            self.sounds.play_death()
            self._respawn_player()

    def _save_high_score(self: Self) -> list[dict[str, int]]:
        """Save the current score to the high scores list.

        Returns:
            The updated high scores list, sorted descending by score.

        """
        max_high_scores = 10
        try:
            existing = self.saves.load('high_scores')
            scores: list[dict[str, int]] = existing.get('scores', [])
        except SaveNotFoundError:
            scores = []

        scores.append({'score': self.player.score})
        scores.sort(key=lambda entry: entry.get('score', 0), reverse=True)
        scores = scores[:max_high_scores]

        self.saves.save('high_scores', {'scores': scores})
        log.info('Saved high score: %d (total entries: %d)', self.player.score, len(scores))
        return scores

    def _respawn_player(self: Self) -> None:
        """Respawn the player with a fade-out/fade-in animation."""
        self.player.is_respawning = True
        self.player.velocity_x = 0.0
        self.player.velocity_y = 0.0
        self.player.stop_horizontal()  # Clear AccelerationBehavior target

        # Fade out, reposition, fade in
        respawn_x = max(0, self.player.world_x - RESPAWN_OFFSET)

        def _reposition_and_fade_in() -> None:
            self.player.world_x = respawn_x
            self.player.world_y = GROUND_Y - PLAYER_HEIGHT
            self.player.on_ground = True
            self.player.is_respawning = False
            # Fade back in
            self.tweens.tween(
                target=self.player,
                property_name='alpha',
                end_value=255.0,
                duration=0.3,
                easing='ease_out_quad',
                on_complete=self._restore_input_after_respawn,
            )

        # Fade out
        self.tweens.tween(
            target=self.player,
            property_name='alpha',
            end_value=0.0,
            duration=0.2,
            easing='ease_in_quad',
            on_complete=_reposition_and_fade_in,
        )

    def _restore_input_after_respawn(self: Self) -> None:
        """Restore movement input state after respawn animation completes.

        Movement is now frame-driven via ActionMap in dt_tick, so
        this just marks respawn as complete. dt_tick will pick up
        held keys on the next frame.
        """

    def _pause_game(self: Self) -> None:
        """Pause the game by switching to the built-in pause scene."""
        pause_scene = PauseScene(options=self.options)
        self.next_scene = pause_scene

    # -----------------------------------------------------------------------
    # Input handling (unified via ActionMap)
    # -----------------------------------------------------------------------

    def _process_movement_input(self: Self) -> None:
        """Apply held movement actions from ActionMap each frame."""
        self.actions.begin_frame()
        if self.player.is_respawning:
            return
        if self.actions.is_held('move_right'):
            self.player.move_right()
        elif self.actions.is_held('move_left'):
            self.player.move_left()
        else:
            self.player.stop_horizontal()

    def _update_voice_assistant(self: Self) -> None:
        """Check for completed voice assistant responses."""
        if self.voice_assistant is not None:
            self.voice_assistant.update()

    @override
    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Handle keyboard key presses via ActionMap.

        Movement is handled frame-driven in dt_tick via is_held().
        One-shot actions (jump, pause, quit) fire here on press.

        Args:
            event: The key down event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action == 'jump':
            if self.player.on_ground:
                self.sounds.play_jump()
            self.player.jump()
        elif action == 'pause':
            self._pause_game()
        elif action == 'quit':
            self.next_scene = None
        elif action is None:
            super().on_key_down_event(event)

    @override
    def on_key_up_event(self: Self, event: HashableEvent) -> None:
        """Handle keyboard key releases.

        Args:
            event: The key up event.

        """
        self.actions.handle_event(event)

    @override
    def on_controller_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle controller button presses via ActionMap.

        Args:
            event: The controller button down event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action == 'jump':
            if self.player.on_ground:
                self.sounds.play_jump()
            self.player.jump()
        elif action == 'mic_toggle' and self.voice_assistant is not None:
            self.voice_assistant.start_listening()

    @override
    def on_controller_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle controller button releases.

        Args:
            event: The controller button up event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action == 'mic_toggle' and self.voice_assistant is not None:
            self.voice_assistant.stop_listening_and_respond()

    @override
    def on_joy_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button presses (pygame-ce uses joystick API).

        Args:
            event: The joystick button down event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action == 'jump':
            if self.player.on_ground:
                self.sounds.play_jump()
            self.player.jump()
        elif action == 'mic_toggle' and self.voice_assistant is not None:
            self.voice_assistant.start_listening()

    @override
    def on_joy_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button releases.

        Args:
            event: The joystick button up event.

        """
        self.actions.handle_event(event)
        action = self.actions.get_action(event)
        if action == 'mic_toggle' and self.voice_assistant is not None:
            self.voice_assistant.stop_listening_and_respond()

    @override
    def on_joy_axis_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick axis motion.

        Args:
            event: The joystick axis motion event.

        """
        self.actions.handle_event(event)

    # -----------------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------------

    @override
    def render(self: Self, screen: pygame.Surface) -> None:
        """Render the game scene.

        Draws background, sprites, and HUD overlay.

        Args:
            screen: The display surface to render to.

        """
        # Fill with sky color
        screen.fill(SKY_COLOR)

        # Draw all sprites via the engine's LayeredDirty system
        self.all_sprites.clear(screen, self.background)
        self.rects = self.all_sprites.draw(screen)

        # Draw pits AFTER sprites so they render on top of the parallax sand,
        # but only in gaps between ground segments (ground sprites are opaque
        # and already drawn, so they mask the pit fill where ground exists).
        self._draw_pits(screen)
        # Re-draw player on top of pits so they're visible when falling in
        screen.blit(self.player.image, self.player.rect)

        # Draw HUD on top
        self._draw_hud(screen)

        # Force full-screen update (parallax will change every frame in Phase 3)
        self.rects = None

    def _draw_pits(self: Self, screen: pygame.Surface) -> None:
        """Draw dark pits in gaps between ground segments.

        Args:
            screen: The display surface to draw on.

        """
        if not self.ground_sprites:
            return

        sorted_segments = sorted(self.ground_sprites, key=lambda segment: segment.world_x)

        for index in range(len(sorted_segments) - 1):
            current_segment = sorted_segments[index]
            next_segment = sorted_segments[index + 1]

            gap_left_world = current_segment.world_x + current_segment.segment_width
            gap_right_world = next_segment.world_x

            if gap_right_world <= gap_left_world:
                continue

            gap_left_screen, _ = self.camera.apply(gap_left_world, 0)
            gap_right_screen, _ = self.camera.apply(gap_right_world, 0)
            gap_width = gap_right_screen - gap_left_screen

            if gap_right_screen < 0 or gap_left_screen > self.screen_width:
                continue

            pit_depth = SCREEN_HEIGHT - GROUND_Y

            # Dark fill
            pygame.draw.rect(
                screen,
                PIT_WALL_COLOR,
                (gap_left_screen, GROUND_Y, gap_width, pit_depth),
            )

            # Thin edge lines for definition
            pygame.draw.line(
                screen,
                PIT_EDGE_COLOR,
                (gap_left_screen, GROUND_Y),
                (gap_left_screen, SCREEN_HEIGHT),
                2,
            )
            pygame.draw.line(
                screen,
                PIT_WALL_SHADOW,
                (gap_right_screen - 1, GROUND_Y),
                (gap_right_screen - 1, SCREEN_HEIGHT),
                2,
            )

            # Dark floor
            pygame.draw.rect(
                screen,
                PIT_FLOOR_COLOR,
                (gap_left_screen, SCREEN_HEIGHT - 4, gap_width, 4),
            )

    def _draw_hud(self: Self, screen: pygame.Surface) -> None:
        """Draw the heads-up display showing score and lives.

        Args:
            screen: The display surface to draw on.

        """
        if self.hud_font is None:
            return

        score_text = f'Score: {self.player.score}'
        lives_text = f'Lives: {self.player.lives}'

        # Shadow for readability
        antialias = True
        shadow_surface = self.hud_font.render(score_text, antialias, HUD_SHADOW_COLOR)
        screen.blit(shadow_surface, (11, 11))
        text_surface = self.hud_font.render(score_text, antialias, HUD_TEXT_COLOR)
        screen.blit(text_surface, (10, 10))

        shadow_surface = self.hud_font.render(lives_text, antialias, HUD_SHADOW_COLOR)
        screen.blit(shadow_surface, (self.screen_width - 109, 11))
        text_surface = self.hud_font.render(lives_text, antialias, HUD_TEXT_COLOR)
        screen.blit(text_surface, (self.screen_width - 110, 10))


def main() -> None:
    """Run the Brave Adventurer game."""
    GameEngine(game=BraveAdventurerScene).start()


if __name__ == '__main__':
    main()
