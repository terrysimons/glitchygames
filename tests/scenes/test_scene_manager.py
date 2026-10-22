"""Tests for SceneManager class functionality."""

import contextlib
import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames import events
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sprites import Sprite

# Constants for magic values
FPS_REFRESH_RATE = 1000


@pytest.fixture(autouse=True)
def restore_scene_manager_options(mocker):
    """Put SceneManager.OPTIONS back after each test.

    Setting a scene manager's game_engine copies the engine's OPTIONS onto the SceneManager
    class; without this, the stand-in engines below would leave their options for later tests.
    """
    mocker.patch.object(SceneManager, 'OPTIONS', SceneManager.OPTIONS)


def _take_events(event_type: int) -> list[pygame.event.Event]:
    """Remove and return the events of one type waiting in pygame's real event queue.

    Returns:
        list[pygame.event.Event]: The events, oldest first.

    """
    return pygame.event.get(eventtype=event_type)


class TestSceneManager:
    """Test SceneManager class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()

        # Create a simple scene manager for testing (centralized mocks handle pygame)
        self.scene_manager = SceneManager()

    def teardown_method(self):
        """Clean up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()

    def test_scene_manager_initialization(self):
        """Test SceneManager initialization."""
        # Reset singleton state for clean test
        SceneManager._reset()

        scene_manager = self.scene_manager

        # Reset any attributes that might have been set by previous tests
        scene_manager._game_engine = None
        scene_manager.active_scene = None

        # Check basic attributes
        assert scene_manager.screen is not None
        assert scene_manager.update_type == 'update'
        assert scene_manager.fps_log_interval_ms == FPS_REFRESH_RATE
        # target_fps may be 60 if game_engine was set in previous tests (singleton behavior)
        assert scene_manager.target_fps in {0, 60}
        assert scene_manager.dt == 0
        assert scene_manager.timer == 0
        assert scene_manager.active_scene is None
        assert scene_manager._game_engine is None

    def test_scene_manager_game_engine_property(self, mocker):
        """Test SceneManager game_engine property."""
        # Reset singleton state for clean test
        SceneManager._reset()

        scene_manager = self.scene_manager

        # Reset any attributes that might have been set by previous tests
        scene_manager._game_engine = None
        scene_manager.active_scene = None

        # Test getting game_engine
        assert scene_manager.game_engine is None

        # Test setting game_engine with proper OPTIONS structure
        mock_engine = mocker.Mock()
        mock_engine.OPTIONS = {
            'update_type': 'update',
            'fps_log_interval_ms': FPS_REFRESH_RATE,
            'target_fps': 60,
        }
        scene_manager.game_engine = mock_engine
        assert scene_manager.game_engine == mock_engine

    def test_scene_manager_all_sprites_property(self, mocker):
        """Test SceneManager all_sprites property."""
        scene_manager = self.scene_manager

        # Test with no active scene (clear any previous scene from singleton)
        scene_manager.active_scene = None
        assert scene_manager.all_sprites is None

        # Test with active scene
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        scene_manager.active_scene = mock_scene
        assert scene_manager.all_sprites == mock_scene.all_sprites

    def test_scene_manager_switch_to_scene(self, mocker):
        """Test SceneManager switch_to_scene method."""
        # Reset singleton state for clean test
        SceneManager._reset()

        scene_manager = self.scene_manager
        mock_scene = mocker.Mock()

        # Mock the scene's required attributes
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = pygame.Surface((800, 600))

        # Test switching to a scene
        scene_manager.switch_to_scene(mock_scene)
        assert scene_manager.active_scene == mock_scene

    def test_scene_manager_play(self):
        """Test SceneManager play method."""
        scene_manager = self.scene_manager

        # Set up scene manager to exit immediately to prevent infinite loop
        scene_manager.active_scene = None
        scene_manager.quit_requested = True

        # Test play method (should not raise exceptions)
        scene_manager.play()

    def test_scene_manager_start(self):
        """Test SceneManager start method."""
        scene_manager = self.scene_manager

        # Set up scene manager to exit immediately to prevent infinite loop
        scene_manager.active_scene = None
        scene_manager.quit_requested = True

        # Test start method (should not raise exceptions)
        scene_manager.start()

    def test_scene_manager_stop(self):
        """Test SceneManager stop method."""
        scene_manager = self.scene_manager

        # Test stop method (should not raise exceptions)
        scene_manager.stop()

    def test_scene_manager_terminate(self):
        """Test SceneManager terminate method."""
        scene_manager = self.scene_manager

        # Test terminate method (should not raise exceptions)
        scene_manager.terminate()

    def test_scene_manager_quit(self):
        """quit() posts one QUIT event to pygame's real event queue."""
        scene_manager = self.scene_manager
        _take_events(pygame.QUIT)

        scene_manager.quit()

        assert len(_take_events(pygame.QUIT)) == 1

    def test_scene_manager_quit_game(self):
        """quit_game() posts one QUIT event to pygame's real event queue."""
        scene_manager = self.scene_manager
        _take_events(pygame.QUIT)

        scene_manager.quit_game()

        assert len(_take_events(pygame.QUIT)) == 1

    def test_scene_manager_on_quit_event(self):
        """A QUIT event sets quit_requested."""
        scene_manager = self.scene_manager
        scene_manager.quit_requested = False

        scene_manager.on_quit_event(events.HashableEvent(pygame.QUIT))

        assert scene_manager.quit_requested is True

    def test_scene_manager_on_fps_event(self):
        """An FPS event reaches the active scene, which stores its FPS."""
        scene_manager = self.scene_manager
        scene = Scene()
        scene_manager.switch_to_scene(scene)

        scene_manager.on_fps_event(events.HashableEvent(events.FPSEVENT, fps=60.0))

        assert scene.fps == 60.0

    def test_scene_manager_on_game_event(self, mocker):
        """Test SceneManager on_game_event method."""
        scene_manager = self.scene_manager
        mock_event = mocker.Mock()
        mock_event.subtype = 'test_event'

        # Set up a mock game engine with registered_events and OPTIONS
        mock_engine = mocker.Mock()
        mock_engine.registered_events = {'test_event': mocker.Mock()}
        mock_engine.OPTIONS = {
            'update_type': 'update',
            'fps_log_interval_ms': FPS_REFRESH_RATE,
            'target_fps': 60,
        }
        scene_manager.game_engine = mock_engine

        # Test game event handling: the registered callback gets the event
        scene_manager.on_game_event(mock_event)

        mock_engine.registered_events['test_event'].assert_called_once_with(mock_event)

    def test_scene_manager_register_game_event(self, mocker):
        """Test SceneManager register_game_event method."""
        scene_manager = self.scene_manager
        mock_callback = mocker.Mock()

        # register_game_event asserts game_engine is not None, so provide one
        mock_engine = mocker.Mock()
        mock_engine.OPTIONS = {
            'update_type': 'update',
            'fps_log_interval_ms': FPS_REFRESH_RATE,
            'target_fps': 60,
        }
        scene_manager.game_engine = mock_engine

        # Test registering game event
        scene_manager.register_game_event('test_event', mock_callback)  # type: ignore[invalid-argument-type]
        mock_engine.register_game_event.assert_called_once_with(
            event_type='test_event',
            callback=mock_callback,
        )

    def test_scene_manager_getattr(self):
        """Test SceneManager __getattr__ method."""
        scene_manager = self.scene_manager

        # Test getting non-existent attribute (should raise AttributeError)
        with pytest.raises(AttributeError):
            _ = scene_manager.nonexistent_method

    def test_scene_manager_handle_event(self, mocker):
        """Test SceneManager handle_event method."""
        scene_manager = self.scene_manager
        mock_event = mocker.Mock()
        mock_event.type = pygame.QUIT  # Set a valid event type

        # Test event handling with no active scene (clear any previous scene from singleton)
        scene_manager.active_scene = None
        scene_manager.handle_event(mock_event)

        # Test event handling with active scene
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = []  # Empty list of sprites
        scene_manager.active_scene = mock_scene

        # This should work now that we've commented out the problematic calls
        scene_manager.handle_event(mock_event)

        # Test with a different event type that doesn't trigger the focused sprites logic
        mock_event.type = pygame.KEYUP
        scene_manager.handle_event(mock_event)


class TestPostFpsEvent:
    """SceneManager._post_fps_event posts the FPS from dt, which replays exactly."""

    @pytest.fixture
    def scene_manager(self):
        """A fresh SceneManager, reset afterwards.

        Yields:
            The scene manager.

        """
        SceneManager._reset()
        yield SceneManager()
        SceneManager._reset()

    def test_post_fps_event_reports_the_frame_time_fps(self, scene_manager):
        """The FPS event's value is 1 / dt (dt comes through the frame-time door)."""
        _take_events(events.FPSEVENT)
        scene_manager.dt = 0.02

        scene_manager._post_fps_event()

        (fps_event,) = _take_events(events.FPSEVENT)
        assert fps_event.fps == pytest.approx(50.0)

    def test_post_fps_event_with_zero_dt_reports_zero_without_the_pacing_clock(
        self, scene_manager, mocker
    ):
        """A zero dt gives 0.0, never pygame's real-time Clock.get_fps(), so a replay is exact."""
        _take_events(events.FPSEVENT)
        # A real Clock's methods are read-only; a stand-in with its interface records reads
        scene_manager.clock = mocker.Mock(spec=pygame.time.Clock)
        scene_manager.clock.get_fps.return_value = 123.0
        scene_manager.dt = 0.0

        scene_manager._post_fps_event()

        (fps_event,) = _take_events(events.FPSEVENT)
        assert fps_event.fps == 0.0
        scene_manager.clock.get_fps.assert_not_called()


class TestSceneManagerInternals:
    """Test SceneManager internal methods."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()

        # Create a simple scene manager for testing (centralized mocks handle pygame)
        self.scene_manager = SceneManager()

    def teardown_method(self):
        """Clean up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()

    def test_scene_manager_should_post_fps_event(self):
        """Test SceneManager _should_post_fps_event method."""
        scene_manager = self.scene_manager

        # Set up proper OPTIONS structure
        scene_manager.OPTIONS = {'fps_log_interval_ms': FPS_REFRESH_RATE}  # type: ignore[invalid-assignment]

        # Test FPS event posting logic
        current_time = 1.0
        previous_fps_time = 0.0
        with contextlib.suppress(AttributeError):
            result = scene_manager._should_post_fps_event(current_time, previous_fps_time)
            assert isinstance(result, bool)

    def test_scene_manager_post_fps_event(self):
        """_post_fps_event posts one FPS event to pygame's real event queue."""
        scene_manager = self.scene_manager
        _take_events(events.FPSEVENT)

        scene_manager._post_fps_event()

        assert len(_take_events(events.FPSEVENT)) == 1

    def test_scene_manager_update_scene(self, mocker):
        """Test SceneManager _update_scene method."""
        scene_manager = self.scene_manager

        # _update_scene asserts active_scene is not None, so provide a mock scene
        mock_scene = mocker.Mock()
        scene_manager.active_scene = mock_scene

        scene_manager._update_scene(scene_dt=0.025)
        mock_scene.dt_tick.assert_called_once_with(0.025)

    def test_scene_manager_process_events(self):
        """Test SceneManager _process_events method."""
        scene_manager = self.scene_manager

        # Test event processing
        with contextlib.suppress(AttributeError):
            scene_manager._process_events()

    def test_scene_manager_render_scene(self, mocker):
        """_render_scene updates the active scene, then renders it onto the real display."""
        scene_manager = self.scene_manager

        # _render_scene asserts active_scene is not None, so provide a mock scene
        mock_scene = mocker.Mock()
        mock_scene.rects = []
        scene_manager.active_scene = mock_scene

        scene_manager._render_scene()
        mock_scene.update.assert_called_once()
        mock_scene.render.assert_called_once_with(pygame.display.get_surface())

    def test_scene_manager_render_scene_draws_the_active_scene(self):
        """A real active scene's background and sprites reach the real display."""
        scene_manager = self.scene_manager
        display = pygame.display.get_surface()
        scene = Scene()
        scene.background_color = (10, 20, 30)
        sprite = Sprite(x=40, y=50, width=6, height=4)
        sprite.image.fill((0, 255, 0))
        scene.all_sprites.add(sprite)
        scene_manager.switch_to_scene(scene)
        display.fill((123, 45, 67))

        scene_manager._render_scene()

        sprite_area = display.subsurface((40, 50, 6, 4))
        assert pygame.transform.average_color(sprite_area)[:3] == (0, 255, 0)
        assert tuple(display.get_at((5, 5)))[:3] == (10, 20, 30)

    def test_scene_manager_update_display(self, mocker):
        """Test SceneManager _update_display method."""
        scene_manager = self.scene_manager

        # _update_display asserts active_scene is not None, so provide a mock scene
        mock_scene = mocker.Mock()
        mock_scene.rects = []
        scene_manager.active_scene = mock_scene

        scene_manager._update_display()

    def test_scene_manager_log_quit_info(self):
        """Test SceneManager _log_quit_info method."""
        scene_manager = self.scene_manager

        # Test quit info logging
        scene_manager._log_quit_info()

    def test_scene_manager_reset_scene_timers(self):
        """Test SceneManager _reset_scene_timers method."""
        scene_manager = self.scene_manager

        # Test scene timer reset
        scene_manager._reset_scene_timers()

    def test_scene_manager_log_scene_switch(self, mocker):
        """Test SceneManager _log_scene_switch method."""
        scene_manager = self.scene_manager
        mock_scene = mocker.Mock()

        # Test scene switch logging
        scene_manager._log_scene_switch(mock_scene)

    def test_scene_manager_cleanup_current_scene(self):
        """Test SceneManager _cleanup_current_scene method."""
        scene_manager = self.scene_manager

        # Test current scene cleanup
        scene_manager._cleanup_current_scene()

    def test_switch_to_scene_clears_screen_shake(self):
        """Review focus 3: pause and game over never inherit a running screen shake."""
        from glitchygames.effects.shake import Shake, ShakeStyle

        self.scene_manager.screen_shake.add(
            Shake(style=ShakeStyle.NOISE, strength=5.0, duration=1.0, frequency=5.0)
        )
        self.scene_manager.switch_to_scene(Scene())
        assert not self.scene_manager.screen_shake.is_active

    def test_switch_to_scene_keeps_pulse_but_clears_sustained_rumble(self, mocker):
        """Pause must never leave a controller buzzing, but a death pulse survives game over."""
        device = mocker.Mock()
        self.scene_manager.rumble.set_sustained(low_frequency=0.25, high_frequency=0.05)
        self.scene_manager.rumble.pulse(low_frequency=1.0, high_frequency=0.6, duration=0.8)
        self.scene_manager.switch_to_scene(Scene())
        assert self.scene_manager.rumble.sustained_levels == (0.0, 0.0)
        self.scene_manager.rumble.update(shakers=[], dt=0.0, devices=lambda: [device])
        device.rumble.assert_called_once_with(1.0, 0.6, 800)

    def test_frame_services_advance_screen_shake(self):
        """Test the per-frame services advance the screen shake by the frame time."""
        from glitchygames.effects.shake import Shake, ShakeStyle

        self.scene_manager.screen_shake.add(
            Shake(style=ShakeStyle.NOISE, strength=5.0, duration=0.5, frequency=5.0)
        )
        self.scene_manager.dt = 1.0
        self.scene_manager._update_frame_services()
        assert not self.scene_manager.screen_shake.is_active

    def test_game_engine_options_set_shake_intensity(self, mocker):
        """Test the game engine setter applies the screen shake intensity option."""
        engine = mocker.Mock()
        engine.OPTIONS = {
            'update_type': 'update',
            'fps_log_interval_ms': 1000,
            'screen_shake_intensity': 0.25,
            'rumble_intensity': 0.5,
        }
        self.scene_manager.game_engine = engine
        assert self.scene_manager.screen_shake.intensity == 0.25
        assert self.scene_manager.rumble.intensity == 0.5

    def test_frame_services_drive_rumble(self, mocker):
        """Test the per-frame services feed the screen shake to the rumble controller."""
        update = mocker.patch.object(self.scene_manager.rumble, 'update')
        scene = Scene()
        self.scene_manager.active_scene = scene
        self.scene_manager.dt = 0.0
        self.scene_manager._update_frame_services()
        assert update.call_args.kwargs['shakers'] == [
            self.scene_manager.screen_shake,
            scene.camera.shake_effect,
        ]

    def test_frame_services_rumble_active_scene_camera_shake(self, mocker):
        """Test a camera shake's rumble reaches the engine's controllers."""
        from glitchygames.camera import Camera2D
        from glitchygames.effects.shake import RumbleSettings, Shake, ShakeStyle

        device = mocker.Mock()
        engine = mocker.Mock()
        engine.controller_manager.controllers = {0: device}
        self.scene_manager._game_engine = engine
        scene = Scene()
        scene.camera = Camera2D(screen_width=100, screen_height=100)
        scene.camera.shake_effect.add(
            Shake(
                style=ShakeStyle.NOISE,
                strength=5.0,
                duration=1.0,
                frequency=5.0,
                rumble=RumbleSettings(low_frequency=1.0, high_frequency=1.0),
            )
        )
        self.scene_manager.active_scene = scene
        self.scene_manager.dt = 0.0
        self.scene_manager._update_frame_services()
        device.rumble.assert_called_once()

    def test_live_audio_is_lazy_and_updated_with_pending_transition(self, mocker):
        manager = self.scene_manager
        manager._live_audio = None
        manager._update_frame_services()  # No LiveAudio created by merely running frames
        assert manager._live_audio is None
        live_audio = mocker.Mock()
        manager._live_audio = live_audio
        pending = mocker.Mock()
        manager._pending_transition = (mocker.Mock(), pending)
        manager._update_frame_services()
        assert live_audio.update.call_args.kwargs['active_transitions'][1] is pending
        manager._pending_transition = None
        manager._live_audio = None


class TestSceneManagerEngineAndQuit:
    """Detaching the engine, and QUIT while a sprite has keyboard focus."""

    def setup_method(self):
        """Set up a fresh scene manager (centralized mocks handle pygame)."""
        SceneManager._reset()
        self.scene_manager = SceneManager()

    def teardown_method(self):
        """Reset the singleton for the next test."""
        SceneManager._reset()

    def test_detaching_the_game_engine_keeps_its_settings(self, mocker):
        """Setting game_engine to None forgets the engine; the settings it gave stay."""
        engine = mocker.Mock()
        engine.OPTIONS = {
            'update_type': 'flip',
            'fps_log_interval_ms': 250,
            'target_fps': 30.0,
        }
        self.scene_manager.game_engine = engine

        self.scene_manager.game_engine = None

        assert self.scene_manager.game_engine is None
        assert self.scene_manager.update_type == 'flip'
        assert self.scene_manager.fps_log_interval_ms == 250
        assert self.scene_manager.target_fps == 30.0

    def test_quit_is_handled_while_a_sprite_has_focus(self, mocker):
        """A focused sprite takes key presses, never QUIT: the manager still quits."""
        focused_sprite = mocker.Mock()
        focused_sprite.is_active = True
        scene = mocker.Mock()
        scene.all_sprites = [focused_sprite]
        self.scene_manager.active_scene = scene
        self.scene_manager.quit_requested = False

        self.scene_manager.handle_event(mocker.Mock(type=pygame.KEYDOWN))
        assert self.scene_manager.quit_requested is False
        self.scene_manager.handle_event(mocker.Mock(type=pygame.QUIT))
        assert self.scene_manager.quit_requested is True


class TestSceneShake:
    """Test Scene.shake targeting."""

    def setup_method(self):
        """Reset the singleton so each test starts clean."""
        SceneManager._reset()

    def teardown_method(self):
        """Reset the singleton so no shake leaks between tests."""
        SceneManager._reset()

    @staticmethod
    def _shake():
        from glitchygames.effects.shake import Shake, ShakeStyle

        return Shake(style=ShakeStyle.NOISE, strength=5.0, duration=1.0, frequency=5.0)

    def test_default_camera_is_identity(self):
        scene = Scene()
        assert scene.camera.apply(5.0, 7.0) == (5, 7)

    def test_world_shake_on_unapplied_camera_warns_once(self, caplog):
        scene = Scene()
        scene.scene_manager.active_scene = scene
        with caplog.at_level('WARNING', logger='game.scenes'):
            scene.shake(self._shake())
            scene.shake(self._shake())
        warnings = [record for record in caplog.records if 'WORLD shake' in record.getMessage()]
        assert len(warnings) == 1
        assert 'use ShakeTarget.SCREEN' in warnings[0].getMessage()

    def test_world_shake_on_applied_camera_does_not_warn(self, caplog):
        scene = Scene()
        scene.scene_manager.active_scene = scene
        scene.camera.apply(0.0, 0.0)
        with caplog.at_level('WARNING', logger='game.scenes'):
            scene.shake(self._shake())
        assert not [record for record in caplog.records if 'WORLD shake' in record.getMessage()]

    def test_world_on_inactive_scene_raises(self):
        """Cue callbacks run on a cleaned-up scene; WORLD must fail loudly there."""
        from glitchygames.camera import Camera2D

        scene = Scene()
        scene.camera = Camera2D(screen_width=100, screen_height=100)
        scene.scene_manager.active_scene = None
        with pytest.raises(RuntimeError, match='active'):
            scene.shake(self._shake())

    def test_world_on_active_scene_shakes_camera(self):
        from glitchygames.camera import Camera2D

        scene = Scene()
        scene.camera = Camera2D(screen_width=100, screen_height=100)
        scene.scene_manager.active_scene = scene
        scene.shake(self._shake())
        assert scene.camera.shake_effect.is_active

    def test_screen_works_from_any_scene(self):
        from glitchygames.effects.shake import ShakeTarget

        scene = Scene()
        scene.scene_manager.active_scene = None
        scene.shake(self._shake(), targets=ShakeTarget.SCREEN)
        assert scene.scene_manager.screen_shake.is_active
        scene.scene_manager.screen_shake.clear()
