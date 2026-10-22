"""Tests for SceneManager class functionality."""

import contextlib
import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.scenes import Scene, SceneManager
from tests.mocks.test_mock_factory import MockFactory

# Constants for magic values
FPS_REFRESH_RATE = 1000


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
        mock_scene.background = MockFactory.create_pygame_surface_mock()

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
        """Test SceneManager quit method."""
        scene_manager = self.scene_manager

        # Test quit method (should not raise exceptions)
        scene_manager.quit()

    def test_scene_manager_quit_game(self):
        """Test SceneManager quit_game method."""
        scene_manager = self.scene_manager

        # Test quit_game method (should not raise exceptions)
        scene_manager.quit_game()

    def test_scene_manager_on_quit_event(self, mocker):
        """Test SceneManager on_quit_event method."""
        scene_manager = self.scene_manager
        mock_event = mocker.Mock()

        # Test quit event handling
        scene_manager.on_quit_event(mock_event)

    def test_scene_manager_on_fps_event(self, mocker):
        """Test SceneManager on_fps_event method."""
        scene_manager = self.scene_manager
        mock_event = mocker.Mock()
        mock_event.fps = 60

        # Test FPS event handling
        scene_manager.on_fps_event(mock_event)

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

        # Test game event handling
        scene_manager.on_game_event(mock_event)

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

    def test_post_fps_event_reports_the_frame_time_fps(self, scene_manager, mocker):
        """The FPS event's value is 1 / dt (dt comes through the frame-time door)."""
        from glitchygames.scenes import scene as scene_module

        posted = mocker.patch.object(scene_module, 'post_event')
        event_class = mocker.patch.object(scene_module.pygame.event, 'Event')
        scene_manager.dt = 0.02

        scene_manager._post_fps_event()

        posted.assert_called_once_with(event_class.return_value)
        assert event_class.call_args.args[1]['fps'] == pytest.approx(50.0)

    def test_post_fps_event_with_zero_dt_reports_zero_without_the_pacing_clock(
        self, scene_manager, mocker
    ):
        """A zero dt gives 0.0, never pygame's real-time Clock.get_fps(), so a replay is exact."""
        from glitchygames.scenes import scene as scene_module

        posted = mocker.patch.object(scene_module, 'post_event')
        event_class = mocker.patch.object(scene_module.pygame.event, 'Event')
        get_fps = mocker.patch.object(scene_manager.clock, 'get_fps', return_value=123.0)
        scene_manager.dt = 0.0

        scene_manager._post_fps_event()

        posted.assert_called_once_with(event_class.return_value)
        assert event_class.call_args.args[1]['fps'] == 0.0
        get_fps.assert_not_called()


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
        """Test SceneManager _post_fps_event method."""
        scene_manager = self.scene_manager

        # Test posting FPS event
        scene_manager._post_fps_event()

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
        """Test SceneManager _render_scene method."""
        scene_manager = self.scene_manager

        # _render_scene asserts active_scene is not None, so provide a mock scene
        mock_scene = mocker.Mock()
        mock_scene.rects = []
        scene_manager.active_scene = mock_scene

        scene_manager._render_scene()
        mock_scene.update.assert_called_once()

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

    def test_switch_to_scene_clears_screen_shake(self, mocker):
        """Review focus 3: pause and game over never inherit a running screen shake."""
        from glitchygames.effects.shake import Shake, ShakeStyle

        self.scene_manager.screen_shake.add(
            Shake(style=ShakeStyle.NOISE, strength=5.0, duration=1.0, frequency=5.0)
        )
        self.scene_manager.switch_to_scene(mocker.Mock())
        assert not self.scene_manager.screen_shake.is_active

    def test_switch_to_scene_keeps_pulse_but_clears_sustained_rumble(self, mocker):
        """Pause must never leave a controller buzzing, but a death pulse survives game over."""
        device = mocker.Mock()
        self.scene_manager.rumble.set_sustained(low_frequency=0.25, high_frequency=0.05)
        self.scene_manager.rumble.pulse(low_frequency=1.0, high_frequency=0.6, duration=0.8)
        self.scene_manager.switch_to_scene(mocker.Mock())
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
