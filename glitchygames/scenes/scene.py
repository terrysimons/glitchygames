"""Scene and SceneManager classes for the Glitchy Games Engine."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast, override

import pygame

from glitchygames import events
from glitchygames.camera import Camera2D
from glitchygames.collision import CollisionManager
from glitchygames.color import BLACK, RGB_COMPONENT_COUNT
from glitchygames.debug import DebugFrameInfo, DebugOverlay
from glitchygames.effects.shake import ScreenShake, Shake, ShakeTarget
from glitchygames.effects.tween import TweenManager
from glitchygames.events.mouse import MousePointer
from glitchygames.input.action_map import DEFAULT_DEADZONE, normalized_axis_value
from glitchygames.input.rumble import RumbleController, connected_rumble_devices
from glitchygames.interfaces import SceneInterface, SpriteInterface
from glitchygames.pixel_snap import PixelSnapMode, set_active_default_snap_mode
from glitchygames.recording import post_event
from glitchygames.timing import DEFAULT_TARGET_FPS
from glitchygames.world import aim_camera, is_world_positioned, position_world_sprites

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.audio.live import LiveAudio
    from glitchygames.engine import GameEngine
    from glitchygames.recording import GameplayRecorder

LOG = logging.getLogger('game.scenes')
LOG.addHandler(logging.NullHandler())

JITTER_SAMPLE_BUFFER_MAX_SIZE = 512
SHAKE_BORDER_COLOR = (0, 0, 0)  # Fills the strips a SCREEN shake uncovers

# Input dropped while a transition plays (SceneManager._process_transition_events): presses
# and motion, so nothing pressed during a ride acts when it ends. Releases (KEYUP,
# MOUSEBUTTONUP, JOYBUTTONUP, CONTROLLERBUTTONUP, FINGERUP), quit, window, focus and device
# events are still delivered, so held-input state (ActionMap) is never left stuck. Motion back
# to neutral is a release too and is delivered: see is_discarded_during_transition.
# CONTROLLERTOUCHPADUP is a release and is delivered. DROPFILE and DROPTEXT are deliberately
# delivered too, to the arriving scene: a file or text dropped during a ride should land.
TRANSITION_DISCARDED_EVENT_TYPES: frozenset[int] = frozenset({
    pygame.KEYDOWN,
    pygame.TEXTINPUT,
    pygame.MOUSEBUTTONDOWN,
    pygame.MOUSEMOTION,
    pygame.MOUSEWHEEL,
    pygame.JOYBUTTONDOWN,
    pygame.JOYAXISMOTION,
    pygame.JOYHATMOTION,
    pygame.JOYBALLMOTION,
    pygame.CONTROLLERBUTTONDOWN,
    pygame.CONTROLLERAXISMOTION,
    pygame.FINGERDOWN,
    pygame.FINGERMOTION,
    pygame.TEXTEDITING,
    pygame.CONTROLLERTOUCHPADDOWN,
    pygame.CONTROLLERTOUCHPADMOTION,
    pygame.MULTIGESTURE,
})


# Axis motions whose value is neutral (a stick back at rest) are releases
_AXIS_MOTION_EVENT_TYPES: frozenset[int] = frozenset({
    pygame.JOYAXISMOTION,
    pygame.CONTROLLERAXISMOTION,
})
HAT_CENTRED: tuple[int, int] = (0, 0)


def is_discarded_during_transition(event: pygame.event.Event) -> bool:
    """Report whether a transition frame drops this event.

    Presses and motion (TRANSITION_DISCARDED_EVENT_TYPES) are dropped, except motion back to
    neutral, which releases a held stick or hat: an axis inside ActionMap's DEFAULT_DEADZONE
    (the value ActionMap treats as zero) or a hat at (0, 0).

    Args:
        event: A raw pygame event.

    Returns:
        True if the event is dropped, False if it is delivered.

    """
    if event.type not in TRANSITION_DISCARDED_EVENT_TYPES:
        return False
    if event.type in _AXIS_MOTION_EVENT_TYPES:
        position = normalized_axis_value(event_type=event.type, value=event.value)
        return abs(position) >= DEFAULT_DEADZONE
    if event.type == pygame.JOYHATMOTION:
        return tuple(event.value) != HAT_CENTRED
    return True


class SceneManager(SceneInterface, events.EventManager):
    """Glitchy Games Scene Manager.

    The scene manager is responsible for managing the active scene,
    and for processing events.
    """

    _instance: ClassVar[SceneManager | None] = None
    log: ClassVar[logging.Logger] = LOG
    OPTIONS: ClassVar[dict[str, Any]] = {}

    # The --record-trace recorder (GameEngine.start_trace_recording sets it), else None; _run_frame
    # records each frame with it. A class default so a frame can run without __init__.
    trace_recorder: GameplayRecorder | None = None

    def __new__(cls) -> Self:
        """Create a new instance or return the existing singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance  # type: ignore[return-value] # ty: ignore[invalid-return-type]

    def __init__(self: Self) -> None:
        """Initialize the scene manager."""
        # Prevent re-initialization of singleton
        if hasattr(self, '_initialized'):
            return

        super().__init__()

        # Scene manager terminates on self.next_scene = None
        try:
            self.screen = pygame.display.get_surface()
            if self.screen is None:
                # Display not initialized yet, will be set later
                self.screen = None
        except pygame.error:
            # Display surface quit or not initialized, will be set later
            self.screen = None
        self.update_type: str = 'update'
        self.fps_log_interval_ms: int = 1000
        self.target_fps: float = 0.0
        self.dt: float = 0.0
        self.timer: Any = 0
        self._game_engine: GameEngine | None = None
        self.active_scene: Scene | None = None
        self.next_scene: Scene | None = self.active_scene
        self.previous_scene: Scene | None = self.active_scene
        self.quit_requested: bool = False

        # Scene transition support
        self._active_transition: Any = None  # Transition object during effect
        self._pending_transition: tuple[Any, Any] | None = None  # (next_scene, transition)

        self.clock: pygame.time.Clock = pygame.time.Clock()

        # SCREEN shake lives here (not on a scene) so it outlives scene switches
        self.screen_shake: ScreenShake = ScreenShake()
        # A shaken or overlaid frame was presented, so the display no longer matches the surface
        self._altered_frame_was_presented: bool = False
        self.debug_overlay: DebugOverlay = DebugOverlay()
        self.rumble: RumbleController = RumbleController()
        self._live_audio: LiveAudio | None = None

        # Jitter tracking attributes
        self._jitter_samples: list[int] = []
        self._jitter_last_log_ns: int = 0
        self._jitter_interval_start_ns: int = 0
        self._jitter_late_frames: int = 0
        self._timer_prev_deadline_ns: int | None = None
        # When the last FPS event was posted (perf_counter seconds); start() sets it
        self._previous_fps_event_seconds: float = 0.0

        # Mark as initialized to prevent re-initialization
        self._initialized: bool = True

    @classmethod
    def _reset(cls) -> None:
        """Reset the singleton for testing.

        Clears the singleton instance so the next call to SceneManager()
        creates a freshly initialized instance. This should only be used
        in tests.
        """
        instance = cls._instance
        if instance is not None and hasattr(instance, '_initialized'):
            del instance._initialized
        cls._instance = None

    def update_screen(self) -> None:
        """Update the screen reference when display becomes available."""
        if self.screen is None:
            self.screen = pygame.display.get_surface()

    @property
    def game_engine(self: Self) -> GameEngine | None:
        """The game engine.

        Returns:
            GameEngine | None: The game engine.

        """
        return self._game_engine

    @game_engine.setter
    def game_engine(self: Self, new_engine: GameEngine | None) -> None:
        self._game_engine = new_engine
        if self._game_engine:
            SceneManager.OPTIONS = self._game_engine.OPTIONS  # pyright: ignore[reportConstantRedefinition]
            self.update_type = self.OPTIONS['update_type']
            self.fps_log_interval_ms = self.OPTIONS['fps_log_interval_ms']
            self.target_fps = self.OPTIONS.get('target_fps', DEFAULT_TARGET_FPS)
            self.screen_shake.intensity = self.OPTIONS.get('screen_shake_intensity', 1.0)
            self.rumble.intensity = self.OPTIONS.get('rumble_intensity', 1.0)
            self.debug_overlay.is_visible = bool(self.OPTIONS.get('debug_overlay', False))
        self.log.info(f'Screen update type: {self.update_type}')
        self.log.info(f'FPS Log Interval: {self.fps_log_interval_ms}ms')
        self.log.info(f'Target FPS: {self.target_fps}')

        # Configure performance manager with the same log interval and target FPS
        try:
            from glitchygames.performance import performance_manager

            performance_manager.set_fps_log_interval(self.fps_log_interval_ms)
            performance_manager.set_target_fps(self.target_fps)
        except ImportError:
            pass  # Performance module not available

    # This enables collided_sprites in sprites.py, since SceneManager is
    # not a scene, but is the entry point for event proxies.
    @property
    def all_sprites(self: Self) -> pygame.sprite.LayeredDirty[Any] | None:
        """The active scene's sprite group.

        Returns:
            pygame.sprite.LayeredDirty[Any] | None: The active scene's sprite group.

        """
        if self.active_scene:
            return self.active_scene.all_sprites

        return None

    def request_transition(
        self: Self,
        next_scene: SceneInterface | None,
        transition: Any,
    ) -> None:
        """Request a scene switch with a visual transition effect.

        The transition starts on the next frame. During the transition,
        normal scene updates and rendering are paused.

        Args:
            next_scene: The scene to transition to.
            transition: A Transition object (FadeTransition, SlideTransition, etc.).

        """
        self._pending_transition = (next_scene, transition)

    def _start_transition(self: Self, next_scene: Any, transition: Any) -> None:
        """Capture screenshots and begin a transition effect.

        Args:
            next_scene: The scene to transition to.
            transition: The Transition object.

        """
        old_surface = self._capture_outgoing_scene()

        # Set up the new scene (off-screen) so we can capture it
        self.previous_scene = self.active_scene
        self._clear_outgoing_scene_pending_switch()
        self._cleanup_current_scene()
        scene = cast('Scene | None', next_scene)
        self._setup_new_scene(scene)
        self.active_scene = scene
        self._configure_active_scene()

        new_surface = self._capture_arriving_scene()

        # Start the transition effect with both screenshots
        transition.start(old_surface, new_surface)
        self._active_transition = transition

    def _capture_outgoing_scene(self: Self) -> pygame.Surface:
        """Screenshot the scene being left, without its player and without a WORLD shake.

        The player is hidden so the transition can draw its own player overlay without
        doubling, and shown again afterwards. A world-space player is hidden with ``hidden``
        (the engine owns its ``visible``) and re-culled afterwards; a screen-space player's
        ``visible`` is written directly.

        Returns:
            A copy of the screen showing the outgoing scene.

        """
        old_player = getattr(self.active_scene, 'player', None) if self.active_scene else None
        old_player_was_hidden = self._hide_world_player_for_capture(old_player)

        # Clear a WORLD shake so the old-floor screenshot is unshaken.
        camera_was_shaking = False
        if self.active_scene is not None and self.active_scene.camera.shake_effect.is_active:
            camera_was_shaking = True
            self.active_scene.camera.shake_effect.clear()
            self.active_scene.apply_camera_to_sprites()

        recapture_old_scene = bool(
            (old_player is not None or camera_was_shaking) and self.active_scene and self.screen
        )
        if recapture_old_scene:
            # Re-place world sprites (the WORLD shake they were placed with is now cleared);
            # a world-space player is already hidden, so positioning culls it
            self._position_active_world_sprites()
        if old_player is not None:
            if old_player_was_hidden is None:
                old_player.visible = False
            old_player.dirty = 0
        if recapture_old_scene:
            assert self.active_scene is not None
            assert self.screen is not None
            self.active_scene.update()
            self.active_scene.render(self.screen)
        old_surface = self.screen.copy() if self.screen else pygame.Surface((800, 600))
        if old_player is not None:
            if old_player_was_hidden is None:
                old_player.visible = True
            else:
                self._restore_world_player_after_capture(
                    player=old_player, was_hidden=old_player_was_hidden
                )
            old_player.dirty = 2
        return old_surface

    @staticmethod
    def _hide_world_player_for_capture(player: object) -> bool | None:
        """Hide a world-space player with ``hidden`` for a transition capture.

        Returns:
            The player's previous ``hidden`` value, or None when there is no player or it is
            screen space (its ``visible`` is written directly instead).

        """
        if player is None or not is_world_positioned(player):
            return None
        was_hidden = bool(getattr(player, 'hidden', False))
        cast('Any', player).hidden = True
        return was_hidden

    def _restore_world_player_after_capture(
        self: Self, *, player: object, was_hidden: bool
    ) -> None:
        """Give a world-space player back its ``hidden`` value and let the engine re-cull it.

        Positioning again sets ``visible`` from the screen and ``hidden``, so a player off
        screen stays invisible instead of being shown until the next frame.

        Args:
            player: The world-space player.
            was_hidden: Its ``hidden`` value before the capture.

        """
        cast('Any', player).hidden = was_hidden
        self._position_active_world_sprites()

    def _capture_arriving_scene(self: Self) -> pygame.Surface:
        """Screenshot the scene being entered (already set up and active), without its player.

        Snaps the camera to the player position (no lerp) and renders, so the screenshot
        shows the correct view for the transition. The player sprite is hidden during the
        capture (the transition draws its own player overlay) and restored afterwards.

        Returns:
            A copy of the screen showing the arriving scene.

        """
        if self.active_scene and self.screen:
            camera = self.active_scene.camera
            player = getattr(self.active_scene, 'player', None)
            # A world-space player is hidden with hidden (positioning then culls it); a
            # screen-space player's visible is written directly, as it always was
            player_was_hidden = self._hide_world_player_for_capture(player)
            player_was_visible = True
            if player is not None:
                if player_was_hidden is None:
                    player_was_visible = getattr(player, 'visible', True)
                    player.visible = False
                player.dirty = 0
                camera.snap_to(
                    target_x=getattr(player, 'world_x', 0.0),
                    target_y=getattr(player, 'world_y', 0.0),
                )
            self.active_scene.dt_tick(0.001)
            # Place the arriving scene's world sprites, so its screenshot shows them in place
            self._position_active_world_sprites()
            if player is not None:
                if player_was_hidden is None:
                    player.visible = False
                player.dirty = 0
            self.active_scene.update()
            self.active_scene.render(self.screen)
            # Restore the player for when gameplay resumes
            if player is not None:
                if player_was_hidden is None:
                    player.visible = player_was_visible
                else:
                    self._restore_world_player_after_capture(
                        player=player, was_hidden=player_was_hidden
                    )
                player.dirty = 2
        return self.screen.copy() if self.screen else pygame.Surface((800, 600))

    def _finalize_transition(self: Self) -> None:
        """Complete a transition and resume normal scene rendering."""
        self._active_transition = None
        # Force a full redraw of the active scene
        if self.active_scene:
            for sprite in self.active_scene.all_sprites:
                sprite.dirty = max(sprite.dirty, 1)

    def _update_frame_services(self: Self) -> None:
        """Advance services that outlive scenes: screen shake, rumble and live audio."""
        self.debug_overlay.record_frame(frame_seconds=self.dt)
        self.screen_shake.update(self.dt)

        shakers = [self.screen_shake]
        active_camera = self._active_camera()
        if active_camera is not None:
            shakers.append(active_camera.shake_effect)
        controller_manager = getattr(self.game_engine, 'controller_manager', None)
        self.rumble.update(
            shakers=shakers,
            dt=self.dt,
            devices=lambda: connected_rumble_devices(controller_manager),
        )

        # The pending transition counts: a ride creates its motor before transition_to starts it
        if self._live_audio is not None:
            pending_transition = (
                self._pending_transition[1] if self._pending_transition is not None else None
            )
            self._live_audio.update(
                active_scene=self.active_scene,
                previous_scene=self.previous_scene,
                active_transitions=(self._active_transition, pending_transition),
            )

    @property
    def live_audio(self: Self) -> LiveAudio:
        """Live synth voices, created on first use from the engine's reserved channels."""
        if self._live_audio is None:
            from glitchygames.audio.live import LiveAudio

            channels = getattr(self.game_engine, 'live_voice_channels', ())
            self._live_audio = LiveAudio(channel_indices=channels)
        return self._live_audio

    def _debug_frame_info(
        self: Self, *, shake_offset: tuple[float, float], inspected_scene_label: str | None
    ) -> DebugFrameInfo:
        """Gather the per-frame engine readings the debug overlay displays.

        Args:
            shake_offset (tuple[float, float]): The current SCREEN shake offset.
            inspected_scene_label (str | None): Name of the scene the overlay inspects when it
                is not the active scene (a paused game), else None.

        Returns:
            DebugFrameInfo: The readings for this frame.

        """
        live_voice_count = (
            self._live_audio.playing_voice_count if self._live_audio is not None else None
        )
        mouse_position = pygame.mouse.get_pos() if pygame.mouse.get_focused() else None
        return DebugFrameInfo(
            target_fps=float(self.target_fps),
            live_voice_count=live_voice_count,
            rumble_levels=self.rumble.sent_levels,
            screen_shake_offset=shake_offset,
            mouse_position=mouse_position,
            inspected_scene_label=inspected_scene_label,
        )

    def _active_scene_has_focused_sprite(self: Self) -> bool:
        """Report whether a sprite in the active scene has keyboard focus.

        Returns:
            bool: True when any sprite's is_active is True; False with no active scene.

        """
        if self.active_scene is None:
            return False
        # `is True` rather than truthiness: Mock sprites report a truthy Mock for any attribute
        return any(
            getattr(sprite, 'is_active', False) is True for sprite in self.active_scene.all_sprites
        )

    def on_key_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the debug overlay keys, then forward key-down events as the proxy would.

        F3 toggles the overlay and F4 cycles its panels, unless a sprite in the active scene has
        keyboard focus (is_active), so typing into text fields is never intercepted. Every other
        key is routed exactly as `__getattr__` routes on_*_event calls: to the active scene, or
        to the game engine when the scene is missing or lacks the handler.

        Args:
            event (events.HashableEvent): The key-down event.

        Raises:
            AttributeError: If neither the active scene nor the game engine has a handler.

        """
        overlay_keys = {pygame.K_F3, pygame.K_F4}
        if event.key in overlay_keys and not self._active_scene_has_focused_sprite():
            if event.key == pygame.K_F3:
                self.debug_overlay.toggle()
            else:
                self.debug_overlay.cycle_panel()
            return
        if self.active_scene is not None and hasattr(self.active_scene, 'on_key_down_event'):
            # Recorded before dispatch, so a quit-key release knows this scene saw the press.
            # Looked up by name: at runtime an active scene may be any SceneInterface stand-in
            # without record_key_press, but active_scene is annotated Scene, so an isinstance
            # check would be flagged as unnecessary by the type checker
            record_key_press = getattr(self.active_scene, 'record_key_press', None)
            if record_key_press is not None:
                record_key_press(key=event.key)
            self.active_scene.on_key_down_event(event)
        elif self.game_engine is not None and hasattr(self.game_engine, 'on_key_down_event'):
            self.game_engine.on_key_down_event(event)
        else:
            message = (
                f"'{type(self)}' object has no attribute 'on_key_down_event': neither the "
                'active scene nor the game engine provides it'
            )
            raise AttributeError(message)

    def _present_frame(self: Self, *, full_update: bool) -> None:
        """Present the rendered frame, shifted by any active SCREEN shake and overlaid if shown.

        The display surface always holds the clean frame between presents: a shaken or overlaid
        frame is copied, shifted and drawn on for the flip, then restored. Dirty-rect rendering,
        screenshots and transition captures therefore never see the shift, the black strips or
        the debug overlay.

        Args:
            full_update: True to flip the whole display (transitions); False to use the
                configured update type.

        """
        # The overlay also draws during transitions (it reflects active_scene); captures stay clean
        offset_x, offset_y = self.screen_shake.offset
        pixel_offset = (round(offset_x), round(offset_y))
        overlay_visible = self.debug_overlay.is_visible
        if self.screen is not None and (pixel_offset != (0, 0) or overlay_visible):
            clean_frame = self.screen.copy()
            if pixel_offset != (0, 0):
                self.screen.fill(SHAKE_BORDER_COLOR)
                self.screen.blit(clean_frame, pixel_offset)
            if overlay_visible and self.active_scene is not None:
                # A pause screen hands over the paused game, whose frozen picture it shows
                debug_subject = self.active_scene.debug_subject
                inspected_scene_label = (
                    None if debug_subject is self.active_scene else debug_subject.NAME
                )
                self.debug_overlay.draw(
                    self.screen,
                    scene=debug_subject,
                    screen_offset=pixel_offset,
                    frame_info=self._debug_frame_info(
                        shake_offset=(offset_x, offset_y),
                        inspected_scene_label=inspected_scene_label,
                    ),
                )
            pygame.display.flip()
            self.screen.blit(clean_frame, (0, 0))
            self._altered_frame_was_presented = True
            return
        if self._altered_frame_was_presented:
            # The display still shows the last shifted or overlaid frame; the surface holds the
            # clean one, so one full flip replaces it (a dirty-rect update would not).
            self._altered_frame_was_presented = False
            pygame.display.flip()
            return
        if full_update:
            pygame.display.flip()
        else:
            self._update_display()

    @override
    def switch_to_scene(self: Self, next_scene: SceneInterface | None) -> None:
        """Switch to the next scene.

        Args:
            next_scene (SceneInterface | None): The next scene to switch to.

        """
        # Cast to Scene | None for internal use. At runtime, all scenes
        # are Scene instances or mocks that satisfy the Scene interface.
        scene = cast('Scene | None', next_scene)
        if scene != self.active_scene:
            self.screen_shake.clear()  # Pause, game over and direct switches never inherit a shake
            self.rumble.clear_sustained()  # ...nor leave a controller buzzing
            # Track the previous scene BEFORE any cleanup or setup
            self.previous_scene = self.active_scene
            self._clear_outgoing_scene_pending_switch()
            self._reset_scene_timers()
            self._log_scene_switch(scene)
            self._cleanup_current_scene()
            self._setup_new_scene(scene)
            self._log_blocked_events(scene)
            self.active_scene = scene
            self._configure_active_scene()

            # Update performance manager with current scene
            try:
                from glitchygames.performance import performance_manager

                if scene:  # Only track performance for real scenes, not None
                    performance_manager.set_current_scene(scene.NAME)
            except ImportError:
                pass  # Performance module not available

    def _clear_outgoing_scene_pending_switch(self: Self) -> None:
        """Clear the pending switch of the scene being switched away from.

        Its pending switch has been honoured (or superseded by a transition): without this,
        a game that paused via next_scene would pause again one frame after resuming, and a
        scene left through a transition would switch back to a stale next_scene when it is
        returned to. The incoming scene's next_scene is left alone, because bootstrap scenes
        request their real scene from __init__.
        """
        if self.active_scene is not None:
            self.active_scene.next_scene = self.active_scene

    def _switch_to_requested_scene(self: Self) -> None:
        """Perform the plain scene switch the active scene requested via next_scene.

        Runs at the end of a frame, after rendering. A next_scene of None or of the active
        scene itself means no switch is pending.
        """
        if self.active_scene is None:
            return
        requested_scene = self.active_scene.next_scene
        if requested_scene is not None and requested_scene != self.active_scene:
            self.switch_to_scene(requested_scene)

    @override
    def play(self: Self) -> None:
        """Play the game."""
        return self.start()

    def _log_jitter_stats(self: Self, timer: object, wake_ns: int, deadline_ns: int) -> None:
        """Log timer jitter statistics if logging is enabled.

        Args:
            timer: The timer backend instance
            wake_ns: The actual wake time in nanoseconds
            deadline_ns: The target deadline in nanoseconds

        """
        try:
            # Cast timer to Any since it has dynamic methods (ns_now, etc.)
            timer_any: Any = timer
            jitter_ns = max(0, int(wake_ns - deadline_ns))
            buf: list[int] = getattr(self, '_jitter_samples', None) or []
            if not self._jitter_samples:
                self._jitter_samples = buf
                now_init: int = timer_any.ns_now()  # ty: ignore[unresolved-attribute]
                self._jitter_last_log_ns = now_init
                self._jitter_interval_start_ns = now_init
                self._jitter_late_frames = 0
            buf.append(jitter_ns)
            if len(buf) > JITTER_SAMPLE_BUFFER_MAX_SIZE:
                del buf[: len(buf) - JITTER_SAMPLE_BUFFER_MAX_SIZE]
            # Late frame if jitter > 0
            if jitter_ns > 0:
                self._jitter_late_frames = getattr(self, '_jitter_late_frames', 0) + 1
            # Log every fps_log_interval_ms
            interval_ns = int(float(self.fps_log_interval_ms) * 1_000_000)
            now_ns: int = timer_any.ns_now()  # ty: ignore[unresolved-attribute]
            if now_ns - self._jitter_last_log_ns >= interval_ns:
                self._log_jitter_interval(buf, now_ns)
        except (ValueError, TypeError, AttributeError) as jitter_error:
            LOG.debug('Jitter logging error: %s', jitter_error)

    def _log_jitter_interval(self: Self, buf: list[int], now_ns: int) -> None:
        """Log jitter statistics for the current interval and reset counters.

        Args:
            buf: Buffer of jitter sample values in nanoseconds
            now_ns: Current time in nanoseconds

        """
        data = sorted(buf)
        count = len(data)
        if count:
            p50 = data[int(0.50 * (count - 1))]
            p95 = data[int(0.95 * (count - 1))]
            p99 = data[int(0.99 * (count - 1))]
            p100 = data[-1]
            # Compute avg FPS and late-frame percentage over interval
            span_ns = max(1, now_ns - getattr(self, '_jitter_interval_start_ns', now_ns))
            avg_fps = (count * 1_000_000_000) / span_ns
            late = getattr(self, '_jitter_late_frames', 0)
            late_pct = (late / count) * 100.0
            self.log.info(
                f'Timer jitter ns: p50={p50}'
                f' p95={p95} p99={p99}'
                f' max={p100} frames={count}'
                f' avg_fps={avg_fps:.1f}'
                f' late={late_pct:.1f}%',
            )
        self._jitter_last_log_ns = now_ns
        self._jitter_interval_start_ns = now_ns
        self._jitter_late_frames = 0

    def _handle_frame_pacing(
        self: Self,
        timer: object | None,
        period_ns: int,
        prev_deadline_ns: int | None,
    ) -> None:
        """Handle frame pacing via timer or fallback to pygame clock.

        Only paces: the frame is measured afterwards, by _finish_frame, with
        time.perf_counter().

        Args:
            timer: The timer backend instance (or None)
            period_ns: Frame period in nanoseconds (0 if no timer)
            prev_deadline_ns: Previous frame deadline in nanoseconds (or None)

        """
        if timer is not None and period_ns > 0:
            # Cast timer to Any since it has dynamic methods (compute_deadline, etc.)
            timer_any: Any = timer
            deadline_ns: int = timer_any.compute_deadline(prev_deadline_ns, period_ns)  # ty: ignore[unresolved-attribute]
            wake_ns: int = timer_any.sleep_until_next(deadline_ns)  # ty: ignore[unresolved-attribute]
            self._timer_prev_deadline_ns = deadline_ns
            # Deadlines use the timer's own clock; the frame is NOT measured with it. The pygame
            # backend's ns_now() is whole milliseconds (get_ticks() * 1_000_000), so a true
            # 16.67 ms cadence would be measured as 17, 17, 16 ms (58.8, 58.8, 62.5 FPS).
            # _finish_frame measures with time.perf_counter() instead (BUGS.md #26).
            # Optional jitter logging
            if self.OPTIONS.get('log_timer_jitter', False):
                self._log_jitter_stats(timer, wake_ns, deadline_ns)
        # Fallback to pygame clock for FPS measurement if no timer
        elif self.target_fps > 0:
            self.clock.tick(self.target_fps)
        else:
            self.clock.tick()

    def _track_performance(self: Self, processing_time: float) -> None:
        """Feed this frame's FPS to the performance manager.

        Args:
            processing_time: Actual processing time in seconds

        """
        try:
            from glitchygames.performance import performance_manager

            # Deliberately NOT self.clock.get_fps(). pygame's Clock.get_fps():
            #   1. recomputes only every 10 tick() calls, so each value repeats for 10 frames,
            #   2. is 10000 / (milliseconds for the last 10 ticks), so values are quantized
            #      (357 = 10000/28, 385 = 10000/26, 500 = 10000/20, ...), and
            #   3. carries over from the previous scene (the clock is shared), so a new
            #      scene's first samples are stale.
            # self.dt is the frame time _finish_frame measured with time.perf_counter(): the
            # full start-to-start period of the frame just finished.
            current_fps = (1.0 / self.dt) if self.dt > 0 else 0.0
            performance_manager.track_fps_from_event(current_fps, processing_time)
        except ImportError:
            pass  # Performance module not available

    def start(self: Self) -> None:
        """Start the scene manager.

        Each frame starts at the previous frame's closing perf_counter() reading and ends in
        _finish_frame, which sets ``self.dt`` once, to that frame's start-to-start period, so
        logic in frame N receives the time frame N-1 took (engine audit #15).
        """
        frame_start_seconds: float = time.perf_counter()
        self._previous_fps_event_seconds = frame_start_seconds
        # The first frame has no previous frame: its dt is the short time since the reading
        # above, as before
        self.dt = time.perf_counter() - frame_start_seconds

        while self.active_scene is not None and self.quit_requested is False:
            # Frame pacing using timer backend when available
            timer = getattr(self.game_engine, 'timer', None)
            period_ns = 0
            if timer is not None:
                period_ns = timer.start_frame(self.target_fps)

            previous_deadline_ns = getattr(self, '_timer_prev_deadline_ns', None)

            self._run_frame()

            # The frame's processing time: its work, without the pacing sleep that follows
            processing_seconds = time.perf_counter() - frame_start_seconds

            frame_start_seconds = self._finish_frame(
                frame_start_seconds=frame_start_seconds,
                timer=timer,
                period_ns=period_ns,
                previous_deadline_ns=previous_deadline_ns,
                processing_seconds=processing_seconds,
            )

        self._log_quit_info()
        return self.terminate()

    def _finish_frame(
        self: Self,
        *,
        frame_start_seconds: float,
        timer: object | None,
        period_ns: int,
        previous_deadline_ns: int | None,
        processing_seconds: float,
    ) -> float:
        """End the frame: pace, measure it once, then record that one frame time.

        In order: pace (timer backend deadline on the timer's own clock, else the pygame
        clock; target 0 never sleeps) and log timer jitter; read time.perf_counter() once,
        which ends this frame and starts the next; set ``self.dt`` to the start-to-start
        period; record it as the frame's FPS sample and post the FPS event when its
        wall-clock interval has passed. Each frame's ``self.dt`` is set only here, so
        recorded frames sum exactly to elapsed time, and logic and the debug overlay in the
        next frame see the same value the statistics recorded (engine audit #15).

        The statistics are recorded after the closing reading, so their (microseconds of)
        work counts towards the next frame's period rather than going unmeasured.

        Args:
            frame_start_seconds: The perf_counter() reading this frame started at (the
                previous frame's closing reading).
            timer: The timer backend instance (or None).
            period_ns: Frame period in nanoseconds (0 if no timer or uncapped).
            previous_deadline_ns: The previous frame's deadline in nanoseconds (or None).
            processing_seconds: The frame's processing time, without pacing, in seconds.

        Returns:
            The closing perf_counter() reading: the next frame's start.

        """
        self._handle_frame_pacing(
            timer=timer,
            period_ns=period_ns,
            prev_deadline_ns=previous_deadline_ns,
        )

        closing_reading_seconds = time.perf_counter()
        self.dt = closing_reading_seconds - frame_start_seconds

        self._track_performance(processing_time=processing_seconds)
        if self._should_post_fps_event(closing_reading_seconds, self._previous_fps_event_seconds):
            self._post_fps_event()
            self._previous_fps_event_seconds = closing_reading_seconds

        return closing_reading_seconds

    def _run_frame(self: Self) -> None:
        """Run one frame (a transition frame or a scene frame), then record it if recording.

        ``self.dt`` must already hold this frame's delta time. It is read before the frame
        runs, because a scene switch at the end of the frame resets ``self.dt``: the
        recording gets the frame's raw dt. A transition's update receives it as is; scene
        logic and the camera aim receive it capped at the scene's MAX_FRAME_SECONDS
        (_scene_frame_seconds), which a replay re-derives from the scene class's attribute.
        The recorder samples the sprites after rendering, from the scene active at the end of
        the frame (after a switch, the new scene as set up), exactly as the golden-trace
        harness does.
        """
        frame_dt = self.dt
        # During a transition, render the transition effect instead of the scene
        if self._active_transition is not None:
            transition_done = self._active_transition.update(self.dt)
            self._process_transition_events()
            self._update_frame_services()
            self._active_transition.render(self.screen)
            self._present_frame(full_update=True)
            if transition_done:
                self._finalize_transition()
        else:
            self._run_scene_frame()

        if self.trace_recorder is not None:
            self.trace_recorder.record_frame(dt=frame_dt, scene=self.active_scene)

    def _run_scene_frame(self: Self) -> None:
        """Run one non-transition frame of the active scene.

        Starts the camera's frame, updates the scene, processes events, updates frame
        services, aims the camera, positions world sprites, renders and presents the frame,
        then starts a pending transition or performs a requested scene switch. ``self.dt``
        must already hold this frame's delta time. The aim is skipped when the active scene
        was switched mid-frame (during its logic or events, as resuming from the pause screen
        does): that scene ran no logic this frame, so its camera waits for its first dt_tick.
        """
        # Order matters: begin_frame() first, so a camera.update() the game made last frame
        # does not count as this frame's (the double-update warning in aim_camera). Then
        # Scene.dt_tick, events, frame services (shake and rumble, so positioning uses this
        # frame's WORLD shake offset), the camera aim and positioning, so sprites spawned in
        # dt_tick are placed before their first render. Scene.update() runs inside
        # _render_scene, after positioning.
        active_camera = self._active_camera()
        if active_camera is not None:
            active_camera.begin_frame()
        # Logic and the camera aim share one (possibly capped) dt; self.dt stays the raw frame
        # time for the frame services, pacing and FPS statistics
        scene_dt = self._scene_frame_seconds()
        logic_scene = self.active_scene
        self._update_scene(scene_dt=scene_dt)
        self._process_events()
        self._update_frame_services()
        # A scene switched to during this frame (resuming from the pause screen switches while
        # events are processed) ran no logic this frame, so its camera is not aimed either:
        # camera time stays in step with the scene's dt_tick, as when games moved the camera
        # in dt_tick. Its world sprites are still positioned for this frame's render.
        if self.active_scene is logic_scene:
            self._aim_active_camera(scene_dt=scene_dt)
        # The display surface may appear only after startup; positioning needs its size
        self.update_screen()
        self._position_active_world_sprites()
        self._render_scene()
        self._present_frame(full_update=False)

        # Check for pending transition (set by Scene.transition_to)
        if self._pending_transition is not None:
            self._start_transition(*self._pending_transition)
            self._pending_transition = None
        # Check for plain scene switch (no transition, backward compatible)
        else:
            self._switch_to_requested_scene()

    def _active_camera(self: Self) -> Camera2D | None:
        """Return the active scene's camera, or None.

        Every Scene has a camera; a scene stand-in (a SceneInterface that is not a Scene) may
        not, and then the engine's camera steps are skipped, as _activate_scene_snap_mode
        tolerates a stand-in without a snap mode.

        Returns:
            The active scene's Camera2D, or None when there is none.

        """
        return cast('Camera2D | None', getattr(self.active_scene, 'camera', None))

    def _scene_frame_seconds(self: Self) -> float:
        """The dt the active scene's logic and camera aim receive this frame.

        self.dt, capped at the scene's MAX_FRAME_SECONDS when it sets one (a scene stand-in
        without the attribute is not capped). After a hitch the scene advances at most the
        cap, while self.dt keeps the whole frame for pacing, FPS statistics and services.

        Returns:
            The scene's dt in seconds.

        """
        cap = getattr(self.active_scene, 'MAX_FRAME_SECONDS', None)
        if cap is None:
            return self.dt
        return min(self.dt, cap)

    def _aim_active_camera(self: Self, *, scene_dt: float) -> None:
        """Aim the active scene's camera at its camera target (glitchygames.world.aim_camera).

        Args:
            scene_dt: The scene's dt this frame (_scene_frame_seconds).

        """
        camera = self._active_camera()
        if camera is None:
            return
        aim_camera(scene=self.active_scene, camera=camera, dt=scene_dt)

    def _position_active_world_sprites(self: Self) -> None:
        """Place the active scene's world sprites on screen from its camera, and cull them.

        Screen-space sprites are untouched (glitchygames.world.position_world_sprites). Uses
        self.screen as it is (callers refresh it with update_screen() first): without a display
        surface there is nothing to place sprites on, so nothing is done.
        """
        camera = self._active_camera()
        if camera is None or self.screen is None:
            return
        assert self.active_scene is not None
        position_world_sprites(
            sprites=self.active_scene.all_sprites,
            camera=camera,
            screen_size=self.screen.get_size(),
        )

    def stop(self: Self) -> None:
        """Stop the game."""
        return self.terminate()

    @override
    def terminate(self: Self) -> None:
        """Terminate the scene manager."""
        self.switch_to_scene(None)

    def quit(self: Self) -> None:
        """Quit the game."""
        return self.quit_game()

    def quit_game(self: Self) -> None:
        """Quit the game."""
        # put a quit event in the event queue.
        self.log.info('POSTING QUIT EVENT')
        post_event(pygame.event.Event(pygame.QUIT, {}))

    def on_quit_event(self: Self, event: events.HashableEvent) -> None:  # ruff: ignore[unused-method-argument]
        """Handle quit events.

        Args:
            event (pygame.event.Event): The quit event.

        """
        # QUIT             none
        self.quit_requested = True

    def on_fps_event(self: Self, event: events.HashableEvent) -> None:
        """Handle FPS events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # FPSEVENT is pygame.USEREVENT + 1
        if self.active_scene:
            self.active_scene.on_fps_event(event)

    def on_game_event(self: Self, event: events.HashableEvent) -> None:
        """Handle game events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # GAMEEVENT is pygame.USEREVENT + 2
        # Call the event callback if it's registered.
        assert self.game_engine is not None
        try:
            event_subtype: int = getattr(event, 'subtype', 0)
            self.game_engine.registered_events[event_subtype](event)
        except KeyError:
            self.log.error(  # ruff: ignore[error-instead-of-exception]
                'Unregistered Event: %s '
                '(call self.register_game_event(<event subtype>, <event data>))',
                event,
            )

    def register_game_event(self: Self, event_type: int, callback: Callable[..., Any]) -> None:
        """Register a game event.

        Args:
            event_type (int): The event type to register.
            callback (Callable[..., Any]): The callback to call when the event is triggered.

        """
        assert self.game_engine is not None
        self.game_engine.register_game_event(event_type=event_type, callback=callback)

    # If the game hasn't hooked a call, we should check if the scene manager has.
    #
    # This will allow scenes to get pygame events directly, but we can still
    # hook those events in this engine, or in the subclassed game object, too.
    #
    # This allows maximum flexibility of event processing, with low overhead
    # at the expense of a slight layer violation.
    @override
    def __getattr__(self: Self, attr: str) -> Callable[..., Any]:
        """Proxy calls to the active scene.

        Args:
            attr (str): The attribute to proxy.

        Returns:
            Callable[..., Any]: The callable object.

        Raises:
            AttributeError: If the attribute is not an on_*_event method.

        """
        # Attempt to proxy the call to the active scene.
        if attr.startswith('on_') and attr.endswith('_event'):
            try:
                # Pass it to the active scene for handling
                return getattr(self.active_scene, attr)
            except AttributeError:
                # Pass it to the game engine for suppression
                return getattr(self.game_engine, attr)
        else:
            message = f"'{type(self)}' object has no attribute '{attr}'"
            raise AttributeError(message)

    def handle_event(self, event: events.HashableEvent) -> None:
        """Handle pygame events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # Check for focused sprites first
        if self.active_scene and self.active_scene.all_sprites:
            focused_sprites = [
                sprite
                for sprite in self.active_scene.all_sprites
                if hasattr(sprite, 'is_active') and sprite.is_active
            ]

            if focused_sprites and event.type == pygame.KEYDOWN:
                # Scene does not expose a handle_event() method; focused sprites
                # receive key events through the normal event dispatch pipeline.
                return

        # Only process other events if no focused sprites handled it
        if event.type == pygame.QUIT:
            self.log.info('POSTING QUIT EVENT')
            self.quit_requested = True

    def _should_post_fps_event(self, current_time: float, previous_fps_time: float) -> bool:
        """Check if FPS event should be posted.

        Args:
            current_time: Current time in seconds
            previous_fps_time: Previous FPS time in seconds

        Returns:
            True if FPS event should be posted

        """
        # Update FPS measurements at half the log interval for better accuracy
        # but still log at the specified interval
        update_interval_ms = float(self.OPTIONS['fps_log_interval_ms']) / 2.0
        return (current_time - previous_fps_time) * 1000 >= update_interval_ms

    def _post_fps_event(self) -> None:
        """Post FPS event."""
        # Prefer dt-derived FPS when available (fast timer path); fallback to clock
        fps_value = 1.0 / self.dt if hasattr(self, 'dt') and self.dt > 0 else self.clock.get_fps()

        post_event(pygame.event.Event(events.FPSEVENT, {'fps': fps_value}))

    def _update_scene(self, *, scene_dt: float) -> None:
        """Update the active scene.

        Args:
            scene_dt: The scene's dt this frame (_scene_frame_seconds).

        """
        assert self.active_scene is not None
        self.active_scene.dt_tick(scene_dt)

    def _process_events(self) -> None:
        """Process game engine events."""
        if self.game_engine is not None:
            self.game_engine.process_events()

    def _process_transition_events(self) -> None:
        """Drain the event queue during a transition frame.

        Presses and motion (``TRANSITION_DISCARDED_EVENT_TYPES``) are discarded, so input
        pressed during a ride never acts when it ends; motion back to neutral is delivered
        (``is_discarded_during_transition``). Everything else goes through the normal
        GameEngine dispatch: releases (so held keys, including ActionMap state, are never left
        stuck), quit, window, focus and device events. ``_start_transition`` has already made
        the incoming scene the active scene, so the delivered events reach the scene that will
        be active after the transition; the outgoing scene has been cleaned up.
        """
        if self.game_engine is not None:
            self.game_engine.process_events(should_discard=is_discarded_during_transition)

    def _render_scene(self) -> None:
        """Render the active scene."""
        assert self.active_scene is not None
        # Update screen reference if needed
        self.update_screen()
        self.active_scene.update()
        if self.screen is not None:
            self.active_scene.render(self.screen)

    def _update_display(self) -> None:
        """Update the display based on update type."""
        assert self.active_scene is not None
        if self.update_type == 'update':
            # If no dirty rects, update the entire screen to show background
            if not self.active_scene.rects:
                pygame.display.update()
            else:
                pygame.display.update(self.active_scene.rects)
        elif self.update_type == 'flip':
            pygame.display.flip()

    def _log_quit_info(self) -> None:
        """Log quit information."""
        self.log.info(
            f'Game Quitting: Active Scene: {self.active_scene}, '
            f'Quit Requested: {self.quit_requested}',
        )

    def _reset_scene_timers(self) -> None:
        """Reset the scene timer.

        The manager's ``dt`` is left alone: _finish_frame is its only per-frame writer, and
        _configure_active_scene seeds the new scene's own ``dt``.
        """
        self.timer = 0

    def _log_scene_switch(self, next_scene: Scene | None) -> None:
        """Log scene switch information."""
        self.log.info(f'Switching to scene "{next_scene}" from scene "{self.active_scene}"')

    def _cleanup_current_scene(self) -> None:
        """Cleanup the current active scene."""
        if self.active_scene:
            self.active_scene._screenshot = self.active_scene.screenshot  # pyright: ignore[reportPrivateUsage]
            self.log.info(f'Cleaning up active scene {self.active_scene}.')
            self.active_scene.cleanup()

    def _setup_new_scene(self, next_scene: Scene | None) -> None:
        """Set up the new scene.

        Every switch and transition (including resuming a paused scene) passes through here, so
        the incoming scene also forgets the key presses it recorded while it was last active.
        """
        if next_scene:
            self.log.info('Setting up new scene %s.', next_scene)
            # Ensure the new scene has access to the game engine
            if hasattr(self, 'game_engine') and self.game_engine:
                next_scene.game_engine = self.game_engine  # type: ignore[attr-defined] # ty: ignore[invalid-assignment]
            # A press recorded before the scene was left (an ESC that paused it, released in
            # the pause scene) must not let a later release quit. Looked up by name, like
            # record_key_press: the scene may be a SceneInterface stand-in without it
            forget_key_presses = getattr(next_scene, 'forget_key_presses', None)
            if forget_key_presses is not None:
                forget_key_presses()
            # The scene's snap mode is active from setup() on, so positions snapped while it
            # sets itself up (camera.snap_to, collision) use it, not the previous scene's mode
            self._activate_scene_snap_mode(next_scene)
            next_scene.setup()

    def _activate_scene_snap_mode(self, scene: Scene) -> None:
        """Make the scene's PIXEL_SNAP_MODE the default for sprites without their own mode.

        A scene stand-in (a SceneInterface that is not a Scene) without a PixelSnapMode gets
        the engine default, NEAREST_HALF_UP, so the previous scene's mode never leaks into it.

        Args:
            scene: The scene being activated.

        """
        scene_mode = getattr(scene, 'PIXEL_SNAP_MODE', None)
        if not isinstance(scene_mode, PixelSnapMode):
            scene_mode = PixelSnapMode.NEAREST_HALF_UP
        set_active_default_snap_mode(scene_mode)

    def _log_blocked_events(self, next_scene: Scene | None) -> None:
        """Log blocked events for the scene."""
        if next_scene:
            self.log.info(f'Scene {next_scene.name} event block list: ')

            blocked_events: list[int] = []

            [
                blocked_events.append(event) if pygame.event.get_blocked(event) else None
                for event in events.ALL_EVENTS
            ]

            if not blocked_events:
                self.log.info('None')

            for event in blocked_events:
                self.log.info(f'{pygame.event.event_name(event)}: Blocked')

    def _configure_active_scene(self) -> None:
        """Configure the active scene after switching."""
        if self.active_scene:
            # A new scene has not ticked yet; its first frame receives the real frame time
            self.active_scene.dt = 0.0
            self.active_scene.timer = self.timer  # type: ignore[attr-defined] # ty: ignore[invalid-assignment]
            # Don't call setup() here - it's already called in _setup_new_scene()

            self._set_display_caption()
            self.active_scene.load_resources()
            self._configure_scene_fps()
            self._log_scene_rendering_info()
            self._setup_event_proxies()
            self._force_scene_redraw()
            self._redraw_scene_background()
            self._apply_scene_fps()

    def _set_display_caption(self) -> None:
        """Set the display caption for the active scene."""
        assert self.active_scene is not None
        caption = ''

        if self.active_scene.NAME:
            caption = f'{self.active_scene.NAME}'

        if self.active_scene.VERSION:
            caption += f' v{self.active_scene.VERSION}'

        pygame.display.set_caption(caption, caption)

    def _configure_scene_fps(self) -> None:
        """Configure FPS for the scene."""
        assert self.active_scene is not None
        # Command line FPS takes precedence over scene FPS
        # Set the scene's target_fps to match the scene manager's target_fps
        # (which comes from OPTIONS)
        self.active_scene.target_fps = self.target_fps

    def _log_scene_rendering_info(self) -> None:
        """Log scene rendering information."""
        assert self.active_scene is not None
        fps_display = (
            'unlimited' if self.active_scene.target_fps == 0 else f'{self.active_scene.target_fps}'
        )
        self.log.info(
            f'Rendering Scene "{self.active_scene.NAME}({type(self.active_scene)})"'
            f' at {fps_display} FPS',
        )

    def _setup_event_proxies(self) -> None:
        """Set up event proxies for the scene."""
        # This controls how events are marshalled
        self.proxies = [self, self.active_scene]

    def _force_scene_redraw(self) -> None:
        """Force a scene redraw."""
        assert self.active_scene is not None
        self.active_scene.dirty = 1

    def _redraw_scene_background(self) -> None:
        """Redraw the scene background."""
        assert self.active_scene is not None
        # Update screen reference if needed
        self.update_screen()
        # Redraw the new scene's background to clear out any artifacts
        if self.screen is not None:
            self.screen.blit(self.active_scene.background, (0, 0))

    def _apply_scene_fps(self) -> None:
        """Apply scene-specific FPS configuration."""
        # Don't override the scene manager's target_fps with the scene's target_fps
        # The scene manager's target_fps comes from OPTIONS and should be maintained
        # The scene's target_fps is already set by _configure_scene_fps()


class Scene(SceneInterface, SpriteInterface, events.AllEventStubs):
    """Scene object base class.

    Subclass this to properly receive on_*_event() messages automatically.
    """

    log = LOG
    FPS = 0
    NAME = 'Unnamed Scene'
    VERSION = '0.0'
    # A game's preferred default target FPS (0.0 = uncapped); None uses the engine default.
    # An explicit --target-fps on the command line always wins.
    TARGET_FPS: ClassVar[float | None] = None
    # The longest frame time (seconds) this scene's dt_tick and camera aim receive; after a
    # hitch (a window drag, focus loss) they advance at most this much, so physics cannot
    # tunnel. None passes the real frame time. Pacing, FPS statistics and the frame services
    # (shake, rumble, the debug overlay) always see the real frame time.
    MAX_FRAME_SECONDS: ClassVar[float | None] = None
    # How sprites without their own pixel_snap_mode (and the camera and parallax layers) are
    # snapped to whole pixels while this scene runs.
    PIXEL_SNAP_MODE: ClassVar[PixelSnapMode] = PixelSnapMode.NEAREST_HALF_UP

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize the scene.

        Args:
            options (dict[str, Any] | None): The options passed to the game.
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups.

        """
        if options is None:
            options = {'debug_events': False, 'no_unhandled_events': False}

        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        if self.NAME == 'Unnamed Scene':
            self.NAME = type(self).__name__  # pyright: ignore[reportConstantRedefinition]

        super().__init__()

        # Since SceneManager is a singleton, this will ensure that
        # any non-active scene which gets initialized will simply
        # get a copy of the scene manager, rather than overwriting
        # the active scene.
        #
        # This helps us keep the upper layers clean by not requiring
        # new scenes to care about the SceneManager when being
        # instantiated.
        self.target_fps: float = 0.0
        self.fps: float = 0.0
        self.dt: float = 0.0
        self.dt_timer: float = 0.0
        self.tweens: TweenManager = TweenManager()
        self.collisions: CollisionManager = CollisionManager()
        self.dirty = 1
        self.options = options
        self.scene_manager = SceneManager()
        self.name = type(self)
        self._background_color: tuple[int, ...] | None = None
        self._last_fps_log_time: float = 0.0
        self._screenshot: pygame.Surface | None = None
        self.quit_requested: bool = False
        # Keys whose key-down reached this scene and are not yet released (record_key_press)
        self._keys_pressed_in_scene: set[int] = set()
        self._world_shake_warning_logged: bool = False
        self.next_scene: Scene | Self | None = self
        self.rects = None
        self.screen = pygame.display.get_surface()
        assert self.screen is not None
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        # Identity camera for scenes that do not scroll (apply(x, y) returns (x, y)); scrolling
        # games replace it with their own. Never None, so callers need no guards.
        self.camera: Camera2D = Camera2D(
            screen_width=self.screen_width, screen_height=self.screen_height
        )

        # http://n0nick.github.io/blog/2012/06/03/quick-dirty-using-pygames-dirtysprite-layered/
        self.all_sprites = groups

        # Initial screen state.

        self.screen = pygame.display.get_surface()
        assert self.screen is not None
        self.background = pygame.Surface(self.screen.get_size())
        self.background.convert()
        self.background_color = BLACK

        # This allows us to be treated like a sprite
        self.image = self.screen
        self.rect = self.screen.get_rect()

        self.dirty = 1

    @property
    def debug_subject(self: Self) -> Scene:
        """The scene the debug overlay inspects: normally this scene itself.

        A scene that only presents another scene (PauseScene shows a frozen screenshot of the
        paused game) returns that scene, so its hitboxes and physics stay visible and line up
        with the frozen picture.
        """
        return self

    @property
    def screenshot(self: Self) -> pygame.Surface:
        """A screenshot of the scene.

        Returns:
            pygame.Surface: The scene screenshot.

        """
        assert self.screen is not None
        screenshot = pygame.Surface((self.screen_width, self.screen_height))
        screenshot.convert()
        screenshot.blit(self.screen, (0, 0))
        return screenshot

    @property
    def background_color(self: Self) -> tuple[int, ...] | None:
        """The background color.

        Returns:
            tuple[int, ...] | None: The background color.

        """
        return self._background_color

    @background_color.setter
    def background_color(self: Self, new_color: tuple[int, ...]) -> None:
        """Set the background color.

        Normalizes RGB colors to RGBA by appending alpha=0 (fully transparent background).

        Args:
            new_color (tuple[int, ...]): The new background color (RGB or RGBA).

        """
        if len(new_color) == RGB_COMPONENT_COUNT:
            new_color = (*new_color, 0)
        self._background_color = new_color
        assert self._background_color is not None
        assert self.screen is not None
        self.background.fill(self._background_color)
        self.all_sprites.clear(self.screen, self.background)

    def transition_to(self: Self, next_scene: Any, transition: Any) -> None:
        """Switch to another scene with a visual transition effect.

        Args:
            next_scene: The scene to transition to.
            transition: A Transition object (FadeTransition, SlideTransition, etc.).

        """
        self.scene_manager.request_transition(next_scene, transition)

    def setup(self: Self) -> None:
        """Set up the scene."""

    def cleanup(self: Self) -> None:
        """Cleanup the scene."""

    def shake(self: Self, shake: Shake, *, targets: ShakeTarget = ShakeTarget.WORLD) -> None:
        """Start a shake on the world (camera), the whole screen, or both.

        Rumble, if the shake has it, is sent automatically by the scene manager.

        Args:
            shake: The shake to start.
            targets: ShakeTarget.WORLD, ShakeTarget.SCREEN, or both combined with |.

        Raises:
            RuntimeError: If WORLD is requested on a scene that is not active (for example
                from a transition cue, which runs after the scene was cleaned up).

        """
        if ShakeTarget.WORLD in targets:
            if self.scene_manager.active_scene is not self:
                message = f'{self.NAME} is not the active scene; use ShakeTarget.SCREEN'
                raise RuntimeError(message)
            self.camera.shake_effect.add(shake)
            if not self._world_shake_warning_logged and not self._world_shake_moves_anything():
                LOG.warning(
                    'WORLD shake on %s has no effect: no sprites are positioned through its '
                    'camera; use ShakeTarget.SCREEN',
                    self.NAME,
                )
                self._world_shake_warning_logged = True
        if ShakeTarget.SCREEN in targets:
            self.scene_manager.screen_shake.add(shake)

    def _world_shake_moves_anything(self: Self) -> bool:
        """Whether a WORLD shake on this scene's camera would move anything on screen.

        It does when a sprite is positioned through Camera2D.apply(), when the camera scrolls
        background layers, or when the scene has world sprites (the engine places them from
        the camera, shake included, without apply()). Decided when shake() is called.

        Returns:
            True if anything is drawn from this scene's camera.

        """
        return (
            self.camera.has_been_applied
            or self.camera.has_parallax_layers
            or any(is_world_positioned(sprite) for sprite in self.all_sprites)
        )

    def camera_target(self: Self) -> tuple[float, float] | None:
        """The world point the engine aims the camera at this frame, or None (manual camera).

        Override to aim the camera anywhere (a point between two players, a cutscene focus).
        The default returns the camera's follow target position (Camera2D.follow()). The
        engine applies the camera's follow axes to whatever point this returns.

        Returns:
            tuple[float, float] | None: The target's (world_x, world_y), or None when the
                camera follows nothing.

        Raises:
            TypeError: If the follow target has no world_x or world_y.

        """
        target = self.camera.follow_target
        if target is None:
            return None
        world_x = getattr(target, 'world_x', None)
        world_y = getattr(target, 'world_y', None)
        if world_x is None or world_y is None:
            message = f'Camera follow target {type(target).__name__} has no world_x/world_y'
            raise TypeError(message)
        return (float(world_x), float(world_y))

    def apply_camera_to_sprites(self: Self) -> None:
        """Reposition camera-relative sprites from the current camera.

        Default: nothing. Games that place sprites through Camera2D.apply() override this so
        the scene manager can refresh positions (for example, after clearing a WORLD shake
        before a transition screenshot).
        """

    def dt_tick(self: Self, dt: float) -> None:
        """Update the scene's delta time and active tweens.

        Args:
            dt (float): The delta time to update.

        """
        self.dt = dt
        self.dt_timer += self.dt
        self.tweens.update(dt)

    @override
    def update(self: Self) -> None:
        """Update the active scene."""
        # Tweak to enable compound sprites to manage their own subsprites dirty states
        #
        # Ideally we'd just make dirty a property with a setter and getter on each
        # sprite object, but that doesn't work for some reason.
        [sprite.update_nested_sprites() for sprite in self.all_sprites]

        # Update all sprites that are dirty
        [sprite.update() for sprite in self.all_sprites if sprite.dirty]

        # Make all of the new scene's sprites dirty to force a redraw
        if self.dirty:
            for sprite in self.all_sprites:
                sprite.dirty = 1 if not sprite.dirty else sprite.dirty

    @override
    def render(self: Self, screen: pygame.Surface) -> None:
        """Render the active scene.

        Args:
            screen (pygame.Surface): The screen to render to.

        """
        # Use LayeredDirty's clear method for proper background clearing and dirty rect management
        self.all_sprites.clear(screen, self.background)
        self.rects = self.all_sprites.draw(screen)

    def sprites_at_position(self: Self, pos: tuple[int, int]) -> list[Any]:
        """Return the sprites at a given position.

        Args:
            pos (tuple[int, int]): The position to check.

        Returns:
            list[Any]: The sprites at the given position.

        """
        mouse = MousePointer(pos=pos)

        return pygame.sprite.spritecollide(sprite=mouse, group=self.all_sprites, dokill=False)

    def _get_collided_sprites(self, position: tuple[int, int]) -> list[Any]:
        """Get sprites at the given position.

        Args:
            position: The position to check for sprites

        Returns:
            List of sprites at the position

        """
        return self.sprites_at_position(pos=position)

    def _get_focusable_sprites(self, collided_sprites: list[Any]) -> list[Any]:
        """Get focusable sprites from the collided sprites.

        Args:
            collided_sprites: List of sprites that were collided with

        Returns:
            List of focusable sprites

        """
        return [s for s in collided_sprites if hasattr(s, 'focusable') and s.focusable]

    def _get_focused_sprites(self) -> list[Any]:
        """Get currently focused sprites.

        Returns:
            List of currently focused sprites

        """
        return [
            sprite
            for sprite in self.all_sprites
            if hasattr(sprite, 'is_active') and sprite.is_active
        ]

    def _has_focusable_sprites(self, collided_sprites: list[Any]) -> bool:
        """Check if any of the collided sprites are focusable.

        Args:
            collided_sprites: List of sprites that were collided with

        Returns:
            True if any sprite is focusable, False otherwise

        """
        return any(hasattr(sprite, 'focusable') and sprite.focusable for sprite in collided_sprites)

    def _unfocus_sprites(self, focused_sprites: list[Any]) -> None:
        """Unfocus the given sprites.

        Args:
            focused_sprites: List of sprites to unfocus

        """
        for sprite in focused_sprites:
            if hasattr(sprite, 'is_active'):
                self.log.debug(f'Unfocusing {type(sprite).__name__}')
                sprite.is_active = False
                if hasattr(sprite, 'on_focus_lost'):
                    sprite.on_focus_lost()

    def _handle_focus_management(self, collided_sprites: list[Any]) -> None:
        """Handle focus management for mouse clicks.

        Args:
            collided_sprites: List of sprites that were collided with

        """
        focused_sprites = self._get_focused_sprites()

        # If we clicked outside all sprites that can be focused, unfocus them
        if not self._has_focusable_sprites(collided_sprites):
            self.log.debug('Click outside focusable sprites - unfocusing')
            self._unfocus_sprites(focused_sprites)

    def record_key_press(self: Self, *, key: int) -> None:
        """Note that a key-down reached this scene.

        SceneManager calls this for every key-down it routes to the active scene, before the
        scene's own on_key_down_event, so subclasses that override that handler are covered.
        on_key_up_event quits only on the release of a key recorded here.

        Args:
            key: The pygame key code.

        """
        self._keys_pressed_in_scene.add(key)

    def forget_key_presses(self: Self) -> None:
        """Forget every key press recorded by record_key_press.

        SceneManager calls this whenever the scene becomes active (switched to, resumed, or
        the target of a transition), before setup(). A press whose release went to another
        scene would otherwise stay recorded, and a later release of that key (whose press was
        discarded during a transition) would quit.
        """
        self._keys_pressed_in_scene.clear()

    def _handle_quit_key_press(self) -> None:
        """Handle quit key press when no sprites are focused."""
        self.log.info('Quit requested')
        # Post a QUIT event to ensure proper cleanup
        post_event(pygame.event.Event(pygame.QUIT))

    @override
    def on_audio_device_added_event(self: Self, event: events.HashableEvent) -> None:
        """Handle audio device added events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # AUDIODEVICEADDED which, iscapture
        self.log.debug(f'{type(self)}: On Audio Device Added Event {event}')

    @override
    def on_audio_device_removed_event(self: Self, event: events.HashableEvent) -> None:
        """Handle audio device removed events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # AUDIODEVICEREMOVED which, iscapture
        self.log.debug(f'{type(self)}: On Audio Device Removed Event {event}')

    @override
    def on_controller_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle controller button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # CONTROLLERBUTTONDOWN which, button
        self.log.debug(f'{type(self)}: On Controller Button Down Event {event}')

    @override
    def on_controller_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle controller button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # CONTROLLERBUTTONUP which, button
        self.log.debug(f'{type(self)}: On Controller Button Up Event {event}')

    @override
    def on_joy_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle joy button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYBUTTONDOWN    joy, button
        self.log.debug(f'{type(self)}: On Joy Button Down Event {event}')

    @override
    def on_joy_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle joy button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYBUTTONUP      joy, button
        self.log.debug(f'{type(self)}: On Joy Button Up Event {event}')

    @override
    def on_key_up_event(self, event: events.HashableEvent) -> None:
        """Handle key up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(f'{type(self)}: On Key Up Event {event}')

        # Check for focused sprites first
        focused_sprites = self._get_focused_sprites()

        # Only a release whose press this scene received can quit (record_key_press): a key
        # pressed during a transition (the press is discarded) or in a scene that has since
        # been left must not quit from here. Each release consumes its press.
        event_key: int | None = getattr(event, 'key', None)
        was_pressed_in_scene = event_key is not None and event_key in self._keys_pressed_in_scene
        if event_key is not None:
            self._keys_pressed_in_scene.discard(event_key)

        # Only process quit keys if no sprites are focused
        if (
            not focused_sprites
            and was_pressed_in_scene
            and event_key in {pygame.K_q, pygame.K_ESCAPE}
        ):
            self._handle_quit_key_press()

    @override
    def on_menu_item_event(self: Self, event: events.HashableEvent) -> None:
        """Handle menu item events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # MENUITEM         menu, item
        self.log.debug(f'{type(self)}: On Menu Item Event {event}')

    @override
    def on_mouse_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug('=== Scene: Mouse Button Down ===')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        self.log.debug('Click position: %s', event_pos)

        # Get sprites at click position
        collided_sprites = self._get_collided_sprites(event_pos)
        self.log.debug(f'Collided sprites: {[type(s).__name__ for s in collided_sprites]}')
        focusable_sprites = self._get_focusable_sprites(collided_sprites)
        self.log.debug('Focusable sprites: %s', focusable_sprites)

        # Diagnostics: log the top-most collided sprite and its active state
        if collided_sprites:
            top_sprite = collided_sprites[-1]
            self.log.debug(
                f'Top sprite @ DOWN: {type(top_sprite).__name__}, '
                f'active={getattr(top_sprite, "active", None)}, pos={event_pos}',
            )

        # Find currently focused sprites
        focused_sprites = self._get_focused_sprites()
        self.log.debug(f'Currently focused sprites: {[type(s).__name__ for s in focused_sprites]}')

        # Handle focus management
        self._handle_focus_management(collided_sprites)

        # Process the click for collided sprites
        for sprite in collided_sprites:
            if hasattr(sprite, 'on_mouse_button_down_event'):
                sprite.on_mouse_button_down_event(event)

    @override
    def on_mouse_drag_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.debug(f'{type(self)}: Mouse Drag Event: {event} {trigger}')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        # Optimized: Skip expensive collision detection for drag events
        # Most drag handling is done by specific sprite drag handlers
        # (e.g., on_left_mouse_drag_event)
        # Only do collision detection if specifically needed
        collided_sprites = self.sprites_at_position(pos=event_pos)

        # Diagnostics: log the top-most collided sprite and its active state during drag
        if collided_sprites:
            top_sprite = collided_sprites[-1]
            self.log.debug(
                f'Top sprite @ DRAG: {type(top_sprite).__name__}, '
                f'active={getattr(top_sprite, "active", None)}, pos={event_pos}',
            )

        for sprite in collided_sprites:
            sprite.on_mouse_drag_event(event, trigger)

    @override
    def on_mouse_drop_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.debug(f'{type(self)}: Mouse Drop Event: {event} {trigger}')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_mouse_drop_event(event, trigger)

    @override
    def on_left_mouse_drag_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle left mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.debug(f'{type(self)}: Left Mouse Drag Event: {event} {trigger}')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites: list[Any] | None = self.sprites_at_position(pos=event_pos)

        if collided_sprites:
            collided_sprites[-1].on_left_mouse_drag_event(event, trigger)

    @override
    def on_left_mouse_drop_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle left mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.debug(f'{type(self)}: Left Mouse Drop Event: {event} {trigger}')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_left_mouse_drop_event(event, trigger)

    @override
    def on_middle_mouse_drag_event(
        self: Self,
        event: events.HashableEvent,
        trigger: object,
    ) -> None:
        """Handle middle mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.info(f'{type(self)}: Middle Mouse Drag Event: {event} {trigger}')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_drag_event(event, trigger)

    @override
    def on_middle_mouse_drop_event(
        self: Self,
        event: events.HashableEvent,
        trigger: object,
    ) -> None:
        """Handle middle mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.info(f'{type(self)}: Middle Mouse Drop Event: {event} {trigger}')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_drop_event(event, trigger)

    @override
    def on_right_mouse_drag_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle right mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.info(f'{type(self)}: Right Mouse Drag Event: {event} {trigger}')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_drag_event(event, trigger)

    @override
    def on_right_mouse_drop_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle right mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.info(f'{type(self)}: Right Mouse Drop Event: {event} {trigger}')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_drop_event(event, trigger)

    @override
    def on_left_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug(f'{type(self)}: Left Mouse Button Up Event: {event}')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))

        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_left_mouse_button_up_event(event)

    @override
    def on_middle_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle middle mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug(f'{type(self)}: Middle Mouse Button Up Event: {event}')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))

        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_button_up_event(event)

    @override
    def on_right_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle right mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button
        self.log.info(f'{type(self)}: Right Mouse Button Up Event: {event}')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))

        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_button_up_event(event)

    @override
    def on_left_mouse_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug('=== Scene: Left Mouse Button Down ===')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        self.log.debug('Click position: %s', event_pos)

        # Get sprites at click position
        collided_sprites = self._get_collided_sprites(event_pos)
        self.log.debug(f'Collided sprites: {[type(s).__name__ for s in collided_sprites]}')
        focusable_sprites = self._get_focusable_sprites(collided_sprites)
        self.log.debug('Focusable sprites: %s', focusable_sprites)

        # Find currently focused sprites
        focused_sprites = self._get_focused_sprites()
        self.log.debug(f'Currently focused sprites: {[type(s).__name__ for s in focused_sprites]}')

        # Handle focus management
        self._handle_focus_management(collided_sprites)

        # Process the click for collided sprites
        for sprite in collided_sprites:
            if hasattr(sprite, 'on_left_mouse_button_down_event'):
                sprite.on_left_mouse_button_down_event(event)

    @override
    def on_middle_mouse_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle middle mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # MOUSEBUTTONDOWN    pos, button
        self.log.debug(f'{type(self)}: Middle Mouse Button Down Event: {event}')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))

        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_button_down_event(event)

    @override
    def on_right_mouse_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle right mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.info(f'{type(self)}: Right Mouse Button Down Event: {event}')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))

        collided_sprites = self._get_collided_sprites(event_pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_button_down_event(event)

    @override
    def on_sys_wm_event(self: Self, event: events.HashableEvent) -> None:
        """Handle sys wm events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(f'{type(self)}: Sys WM Event: {event}')

    @override
    def on_text_editing_event(self: Self, event: events.HashableEvent) -> None:
        """Handle text editing events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(f'{type(self)}: Text Editing Event: {event}')

    @override
    def on_text_input_event(self: Self, event: events.HashableEvent) -> None:
        """Handle text input events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(f'{type(self)}: Text Input Event: {event}')

    @override
    def on_touch_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle touch down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # TOUCHBUTTONDOWN  touch, pos, button
        self.log.debug(f'{type(self)}: Touch Down Event: {event}')

    @override
    def on_touch_motion_event(self: Self, event: events.HashableEvent) -> None:
        """Handle touch motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # TOUCHMOTION      touch, pos
        self.log.debug(f'{type(self)}: Touch Motion Event: {event}')

    @override
    def on_touch_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle touch up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # TOUCHBUTTONUP    touch, pos
        self.log.debug(f'{type(self)}: Touch Up Event: {event}')

    @override
    def on_user_event(self: Self, event: events.HashableEvent) -> None:
        """Handle user events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # USEREVENT        code
        self.log.debug(f'{type(self)}: User Event: {event}')

    @override
    def on_video_expose_event(self: Self, event: events.HashableEvent) -> None:
        """Handle video expose events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # VIDEOEXPOSE      none
        self.log.debug(f'{type(self)}: Video Expose Event: {event}')

    @override
    def on_video_resize_event(self: Self, event: events.HashableEvent) -> None:
        """Handle video resize events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # VIDEORESIZE      size, w, h
        self.log.debug(f'{type(self)}: Video Resize Event: {event}')

    @override
    def on_window_close_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window close events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWCLOSE      none
        self.log.debug(f'{type(self)}: Window Close Event: {event}')

    @override
    def on_window_enter_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window enter events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWENTER      none
        self.log.debug(f'{type(self)}: Window Enter Event: {event}')

    @override
    def on_window_exposed_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window exposed events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWEXPOSED    none
        self.log.debug(f'{type(self)}: Window Exposed Event: {event}')

    @override
    def on_window_focus_gained_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window focus gained events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWFOCUSGAINED none
        self.log.debug(f'{type(self)}: Window Focus Gained Event: {event}')

    @override
    def on_window_focus_lost_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window focus lost events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWFOCUSLOST  none
        self.log.debug(f'{type(self)}: Window Focus Lost Event: {event}')

    @override
    def on_window_hidden_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window hidden events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWHIDDEN     none
        self.log.debug(f'{type(self)}: Window Hidden Event: {event}')

    @override
    def on_window_hit_test_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window hit test events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWHITTEST    pos
        self.log.debug(f'{type(self)}: Window Hit Test Event: {event}')

    @override
    def on_window_leave_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window leave events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWLEAVE      none
        self.log.debug(f'{type(self)}: Window Leave Event: {event}')

    @override
    def on_window_maximized_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window maximized events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWMAXIMIZED  none
        self.log.debug(f'{type(self)}: Window Maximized Event: {event}')

    @override
    def on_window_minimized_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window minimized events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWMINIMIZED  none
        self.log.debug(f'{type(self)}: Window Minimized Event: {event}')

    @override
    def on_window_moved_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window moved events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWMOVED      pos
        self.log.debug(f'{type(self)}: Window Moved Event: {event}')

    @override
    def on_window_resized_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window resized events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWRESIZED    size, w, h
        self.log.debug(f'{type(self)}: Window Resized Event: {event}')

    @override
    def on_window_restored_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window restored events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWRESTORED   none
        self.log.debug(f'{type(self)}: Window Restored Event: {event}')

    @override
    def on_window_shown_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window shown events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWSHOWN      none
        self.log.debug(f'{type(self)}: Window Shown Event: {event}')

    @override
    def on_window_size_changed_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window size changed events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWSIZECHANGED size, w, h
        self.log.debug(f'{type(self)}: Window Size Changed Event: {event}')

    @override
    def on_window_take_focus_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window take focus events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # WINDOWTAKEFOCUS  none
        self.log.debug(f'{type(self)}: Window Take Focus Event: {event}')

    @override
    def on_quit_event(self: Self, event: events.HashableEvent) -> None:
        """Handle quit events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # QUIT             none
        self.log.debug(f'{type(self)}: {event}')

    @override
    def on_fps_event(self: Self, event: events.HashableEvent) -> None:
        """Handle FPS events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # FPSEVENT is pygame.USEREVENT + 1
        # Log FPS at the specified interval to reduce log spam
        current_time = time.perf_counter()

        # Use the configured log interval instead of hardcoded 1.0 second
        log_interval_seconds = float(self.scene_manager.fps_log_interval_ms) / 1000.0
        if current_time - self._last_fps_log_time >= log_interval_seconds:
            event_fps: float = getattr(event, 'fps', 0.0)
            self.log.info(f'Scene "{self.NAME}" ({type(self)}) FPS: {event_fps}')
            self._last_fps_log_time = current_time

        self.fps = getattr(event, 'fps', 0.0)

    def load_resources(self: Self) -> None:
        """Load the scene's resources."""
        self.log.debug(f'Implement load_resource() in {type(self)}.')

    @override
    def on_key_down_event(self, event: events.HashableEvent) -> None:
        """Handle key down events."""
        self.log.debug(f'{type(self)}: On Key Down Event {event}')

        # Check if focused sprites handle the event
        if self._handle_focused_sprite_events(event):
            return

        # Only process scene-level key events if no focused sprite handled it
        self._handle_scene_key_events(event)

    def _handle_focused_sprite_events(self, event: events.HashableEvent) -> bool:
        """Handle events for focused sprites.

        Args:
            event: The event to handle

        Returns:
            True if a focused sprite handled the event, False otherwise

        """
        # Find the currently focused sprite
        focused_sprites = [
            sprite
            for sprite in self.all_sprites
            if hasattr(sprite, 'is_active') and sprite.is_active
        ]

        if focused_sprites:
            # If we have focused sprites, only they get the events
            for sprite in focused_sprites:
                if hasattr(sprite, 'on_key_down_event'):
                    sprite.on_key_down_event(event)
                    return True  # Stop event propagation after handling

        return False

    def _handle_scene_key_events(self, event: events.HashableEvent) -> None:
        """Handle scene-level key events.

        Args:
            event: The event to handle

        """
        event_key: int | None = getattr(event, 'key', None)
        if event_key == pygame.K_q:
            self.log.info('Quit requested')
            self.quit_requested = True

    def on_text_submit_event(self, text: str) -> None:
        """Handle text submission from MultiLineTextBox.

        Args:
            text (str): The submitted text.

        """
        self.log.info("Text submitted: '%s'", text)

    @override
    def pause(self: Self) -> None:
        """Pause the current scene.

        Default implementation requests a PauseScene for the end of this frame.
        Scenes can override this method to provide custom pause behavior.

        The switch happens after this frame renders (via next_scene), not immediately: pause()
        usually runs during event processing, after sprites have moved this frame, so an
        immediate switch would freeze the previous frame's picture one frame behind the game.

        """
        from .builtin_scenes.pause_scene import PauseScene

        self.next_scene = PauseScene(options=self.options)

        self.log.info('Scene pause requested')

    def resume(self: Self) -> None:
        """Resume the current scene.

        Default implementation switches back to the previous scene.
        Scenes can override this method to provide custom resume behavior.

        """
        if self.scene_manager.previous_scene:
            self.scene_manager.switch_to_scene(self.scene_manager.previous_scene)
            self.log.info('Scene resumed')
        else:
            self.log.warning('No previous scene found to resume')

    def game_over(self: Self) -> None:
        """Handle game over for the current scene.

        Default implementation switches to a GameOverScene.
        Scenes can override this method to provide custom game over behavior.

        """
        from .builtin_scenes.game_over_scene import GameOverScene

        # Create the game over scene
        game_over_scene = GameOverScene(options=self.options)

        # Switch to the game over scene
        self.scene_manager.switch_to_scene(game_over_scene)

        self.log.info('Game over')
