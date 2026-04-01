"""Scene and SceneManager classes for the Glitchy Games Engine."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast, override

import pygame

from glitchygames import events
from glitchygames.collision import CollisionManager
from glitchygames.color import BLACK, RGB_COMPONENT_COUNT
from glitchygames.effects.tween import TweenManager
from glitchygames.events.mouse import MousePointer
from glitchygames.interfaces import SceneInterface, SpriteInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.engine import GameEngine

LOG = logging.getLogger('game.scenes')
LOG.addHandler(logging.NullHandler())

JITTER_SAMPLE_BUFFER_MAX_SIZE = 512


class SceneManager(SceneInterface, events.EventManager):
    """Glitchy Games Scene Manager.

    The scene manager is responsible for managing the active scene,
    and for processing events.
    """

    _instance: ClassVar[SceneManager | None] = None
    log: ClassVar[logging.Logger] = LOG
    OPTIONS: ClassVar[dict[str, Any]] = {}

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
        self.target_fps: int = 0
        self.dt: float = 0.0
        self.timer: Any = 0
        self._game_engine: GameEngine | None = None
        self.active_scene: Scene | None = None
        self.next_scene: Scene | None = self.active_scene
        self.previous_scene: Scene | None = self.active_scene
        self.quit_requested: bool = False

        self.clock: pygame.time.Clock = pygame.time.Clock()

        # Jitter tracking attributes
        self._jitter_samples: list[int] = []
        self._jitter_last_log_ns: int = 0
        self._jitter_interval_start_ns: int = 0
        self._jitter_late_frames: int = 0
        self._timer_prev_deadline_ns: int | None = None

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
        """Return the game engine.

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
            self.target_fps = self.OPTIONS.get('target_fps', 60)
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
        """Return the active scene's sprite group.

        Returns:
            pygame.sprite.LayeredDirty[Any] | None: The active scene's sprite group.

        """
        if self.active_scene:
            return self.active_scene.all_sprites

        return None

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
            # Track the previous scene BEFORE any cleanup or setup
            self.previous_scene = self.active_scene
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
        frame_start_ns: int,
    ) -> None:
        """Handle frame pacing via timer or fallback to pygame clock.

        Args:
            timer: The timer backend instance (or None)
            period_ns: Frame period in nanoseconds (0 if no timer)
            prev_deadline_ns: Previous frame deadline in nanoseconds (or None)
            frame_start_ns: Frame start time in nanoseconds

        """
        if timer is not None and period_ns > 0:
            # Cast timer to Any since it has dynamic methods (compute_deadline, etc.)
            timer_any: Any = timer
            deadline_ns: int = timer_any.compute_deadline(prev_deadline_ns, period_ns)  # ty: ignore[unresolved-attribute]
            wake_ns: int = timer_any.sleep_until_next(deadline_ns)  # ty: ignore[unresolved-attribute]
            self._timer_prev_deadline_ns = deadline_ns
            # Update dt based on actual pacing wake time for next iteration
            self.dt = (wake_ns - frame_start_ns) / 1e9
            # Optional jitter logging
            if self.OPTIONS.get('log_timer_jitter', False):
                self._log_jitter_stats(timer, wake_ns, deadline_ns)
        # Fallback to pygame clock for FPS measurement if no timer
        elif self.target_fps > 0:
            self.clock.tick(self.target_fps)
        else:
            self.clock.tick()

    def _track_performance(
        self: Self,
        timer: object | None,
        period_ns: int,
        processing_time: float,
    ) -> None:
        """Feed FPS data to the performance manager.

        Args:
            timer: The timer backend instance (or None)
            period_ns: Frame period in nanoseconds (0 if no timer)
            processing_time: Actual processing time in seconds

        """
        try:
            from glitchygames.performance import performance_manager

            # If timer pacing is enabled, compute FPS from dt; otherwise use pygame clock
            if timer is not None and period_ns > 0:
                current_fps = (1.0 / self.dt) if self.dt > 0 else 0.0
            else:
                current_fps = self.clock.get_fps()
            performance_manager.track_fps_from_event(current_fps, processing_time)
        except ImportError:
            pass  # Performance module not available

    def start(self: Self) -> None:
        """Start the scene manager."""
        previous_time: float = time.perf_counter()
        previous_fps_time: float = previous_time
        current_time: float = previous_time

        while self.active_scene is not None and self.quit_requested is False:
            # Frame pacing using timer backend when available
            timer = getattr(self.game_engine, 'timer', None)
            period_ns = 0
            if timer is not None:
                period_ns = timer.start_frame(int(self.target_fps))

            prev_deadline_ns = getattr(self, '_timer_prev_deadline_ns', None)
            frame_start_ns = timer.ns_now() if timer is not None else 0

            now: float = time.perf_counter()
            self.dt = now - previous_time
            previous_time = now

            # Start timing ONLY the actual processing (after tick_clock)
            processing_start = time.perf_counter()

            self._update_scene()
            self._process_events()
            self._render_scene()
            self._update_display()

            self._handle_frame_pacing(timer, period_ns, prev_deadline_ns, frame_start_ns)

            # End timing the actual processing
            processing_end = time.perf_counter()
            actual_processing_time = processing_end - processing_start

            self._track_performance(timer, period_ns, actual_processing_time)

            if self._should_post_fps_event(current_time, previous_fps_time):
                self._post_fps_event()
                previous_fps_time = current_time

            # Only switch scenes if the current scene has a different next_scene
            if (
                self.active_scene.next_scene is not None
                and self.active_scene.next_scene != self.active_scene
            ):
                self.switch_to_scene(self.active_scene.next_scene)
            current_time = time.perf_counter()

        self._log_quit_info()
        return self.terminate()

    def _update_timing(self, previous_time: float, current_time: float) -> tuple[float, float]:
        """Update timing variables for the game loop.

        Args:
            previous_time: Previous frame time
            current_time: Current frame time

        Returns:
            Tuple of (updated_previous_time, updated_current_time)

        """
        now: float = time.perf_counter()
        self.dt = now - previous_time
        return current_time, now

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
        pygame.event.post(pygame.event.Event(pygame.QUIT, {}))

    def on_quit_event(self: Self, event: events.HashableEvent) -> None:  # noqa: ARG002
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
            self.log.error(  # noqa: TRY400
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

        pygame.event.post(pygame.event.Event(events.FPSEVENT, {'fps': fps_value}))

    def _tick_clock(self) -> None:
        """Tick the clock for FPS control."""
        # If target_fps is 0, don't limit the frame rate (unlimited FPS)
        if self.target_fps > 0:
            self.clock.tick(self.target_fps)
        else:
            # For unlimited FPS, just tick without limiting
            self.clock.tick()

        # Feed FPS data directly to performance manager for accurate tracking
        try:
            from glitchygames.performance import performance_manager

            current_fps = self.clock.get_fps()
            # Calculate actual frame time for spare time calculation
            frame_time = self.dt if hasattr(self, 'dt') else 0.0
            if frame_time > 0:
                LOG.debug('frame_time=%.1fms, fps=%.1f', frame_time * 1000, current_fps)
            performance_manager.track_fps_from_event(current_fps, frame_time)
        except ImportError:
            pass  # Performance module not available

    def _update_scene(self) -> None:
        """Update the active scene."""
        assert self.active_scene is not None
        self.active_scene.dt_tick(self.dt)

    def _process_events(self) -> None:
        """Process game engine events."""
        if self.game_engine is not None:
            self.game_engine.process_events()

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
        """Reset scene timers."""
        self.dt = 0.0
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
        """Set up the new scene."""
        if next_scene:
            self.log.info('Setting up new scene %s.', next_scene)
            # Ensure the new scene has access to the game engine
            if hasattr(self, 'game_engine') and self.game_engine:
                next_scene.game_engine = self.game_engine  # type: ignore[attr-defined] # ty: ignore[invalid-assignment]
            next_scene.setup()

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
            self.active_scene.dt = self.dt
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
        self.target_fps: int = 0
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
        self.next_scene: Scene | Self | None = self
        self.rects = None
        self.screen = pygame.display.get_surface()
        assert self.screen is not None
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

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
    def screenshot(self: Self) -> pygame.Surface:
        """Return a screenshot of the scene.

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
        """Return the background color.

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

    def setup(self: Self) -> None:
        """Set up the scene."""

    def cleanup(self: Self) -> None:
        """Cleanup the scene."""

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

    def _handle_quit_key_press(self) -> None:
        """Handle quit key press when no sprites are focused."""
        self.log.info('Quit requested')
        # Post a QUIT event to ensure proper cleanup
        pygame.event.post(pygame.event.Event(pygame.QUIT))

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

        # Only process quit keys if no sprites are focused
        event_key: int | None = getattr(event, 'key', None)
        if not focused_sprites and event_key in {pygame.K_q, pygame.K_ESCAPE}:
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

        Default implementation switches to a PauseScene.
        Scenes can override this method to provide custom pause behavior.

        """
        from .builtin_scenes.pause_scene import PauseScene

        # Create the pause scene
        pause_scene = PauseScene(options=self.options)

        # Switch to the pause scene
        self.scene_manager.switch_to_scene(pause_scene)

        self.log.info('Scene paused')

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
