"""Tests for the debug overlay's SceneManager integration (keys, flag, frame history, present)."""

import argparse
import types

import pygame
import pytest

from glitchygames.camera import Camera2D
from glitchygames.debug import DebugFrameInfo
from glitchygames.debug.overlay import DebugOverlay, DebugPanel
from glitchygames.engine import GameEngine
from glitchygames.events import HashableEvent
from glitchygames.scenes import Scene, SceneManager
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene

SCREEN_SIZE = (64, 48)
BACKGROUND_COLOR = (0, 0, 0)
MARKER_COLOR = (255, 255, 255)
MARKER_POSITION = (10, 20)
SHAKE_OFFSET = (0.0, 4.0)


@pytest.fixture(autouse=True)
def initialized_pygame():
    """Initialise pygame (fonts) for tests that draw real text."""
    pygame.init()


@pytest.fixture
def scene(mocker):
    """A minimal scene with a real camera, no sprites and a recording key handler.

    Returns:
        A SimpleNamespace standing in for the active scene.

    """
    fake_scene = types.SimpleNamespace(
        camera=Camera2D(*SCREEN_SIZE),
        all_sprites=[],
        on_key_down_event=mocker.Mock(),
        NAME='FakeScene',
    )
    fake_scene.debug_subject = fake_scene  # a normal scene inspects itself
    return fake_scene


@pytest.fixture
def manager(scene):
    """A fresh SceneManager with a real 64x48 screen and the fake scene active.

    Yields:
        The SceneManager singleton.

    """
    SceneManager._reset()
    scene_manager = SceneManager()
    scene_manager.screen = pygame.Surface(SCREEN_SIZE)
    scene_manager.screen.set_at(MARKER_POSITION, MARKER_COLOR)
    scene_manager.active_scene = scene
    yield scene_manager
    SceneManager._reset()


def key_down(key):
    """Build a key-down event.

    Args:
        key: The pygame key constant.

    Returns:
        A HashableEvent.

    """
    return HashableEvent(pygame.KEYDOWN, key=key, mod=0, unicode='')


def pixels_of(surface):
    """Read a surface's pixels as bytes.

    Args:
        surface: The surface to read.

    Returns:
        The raw pixel bytes.

    """
    return pygame.image.tobytes(surface, 'RGB')


def capture_at_flip(mocker, manager):
    """Patch pygame.display.flip to record manager.screen's pixels when it is called.

    Args:
        mocker: The pytest-mock fixture.
        manager: The SceneManager whose screen is inspected.

    Returns:
        The list that receives one pixel snapshot per flip.

    """
    snapshots = []
    mocker.patch(
        'pygame.display.flip',
        side_effect=lambda: snapshots.append(pixels_of(manager.screen)),
    )
    return snapshots


class TestDebugOverlayFlag:
    """The --debug-overlay flag and the game_engine setter."""

    @staticmethod
    def _parse(arguments):
        parser = argparse.ArgumentParser()
        GameEngine.args(parser)
        return vars(parser.parse_args(arguments))

    def test_defaults_to_off(self):
        """Test the flag is off unless passed."""
        assert self._parse([])['debug_overlay'] is False

    def test_flag_turns_it_on(self):
        """Test passing the flag sets the option."""
        assert self._parse(['--debug-overlay'])['debug_overlay'] is True

    @pytest.mark.parametrize('option_value', [True, False])
    def test_game_engine_setter_applies_the_option(self, manager, mocker, option_value):
        """Test the setter makes the overlay's visibility match the option."""
        manager.debug_overlay.is_visible = not option_value
        engine = mocker.Mock()
        engine.OPTIONS = {
            'update_type': 'update',
            'fps_log_interval_ms': 1000,
            'debug_overlay': option_value,
        }
        manager.game_engine = engine
        assert manager.debug_overlay.is_visible is option_value

    def test_game_engine_setter_defaults_to_hidden(self, manager, mocker):
        """Test an engine whose options lack the key leaves the overlay hidden."""
        manager.debug_overlay.is_visible = True
        engine = mocker.Mock()
        engine.OPTIONS = {'update_type': 'update', 'fps_log_interval_ms': 1000}
        manager.game_engine = engine
        assert manager.debug_overlay.is_visible is False

    def test_manager_owns_an_overlay(self, manager):
        """Test the manager creates a hidden DebugOverlay."""
        assert isinstance(manager.debug_overlay, DebugOverlay)
        assert manager.debug_overlay.is_visible is False


class TestOverlayKeys:
    """F3 and F4 handling, and routing of every other key."""

    def test_f3_toggles_and_is_not_forwarded(self, manager, scene):
        """Test F3 toggles the overlay and the scene never sees it."""
        manager.on_key_down_event(key_down(pygame.K_F3))
        assert manager.debug_overlay.is_visible is True
        scene.on_key_down_event.assert_not_called()

    def test_f4_cycles_and_is_not_forwarded(self, manager, scene):
        """Test F4 cycles the panel and the scene never sees it."""
        manager.on_key_down_event(key_down(pygame.K_F4))
        assert manager.debug_overlay.panel is DebugPanel.COLLISION
        scene.on_key_down_event.assert_not_called()

    def test_other_keys_are_forwarded_unchanged(self, manager, scene):
        """Test any other key reaches the active scene as the same event."""
        event = key_down(pygame.K_a)
        manager.on_key_down_event(event)
        scene.on_key_down_event.assert_called_once_with(event)
        assert manager.debug_overlay.is_visible is False
        assert manager.debug_overlay.panel is DebugPanel.ALL

    def test_f3_reaches_a_focused_sprite_and_does_not_toggle(self, manager, scene):
        """Test F3 is forwarded, not intercepted, while a sprite has keyboard focus."""
        scene.all_sprites.append(types.SimpleNamespace(is_active=True))
        event = key_down(pygame.K_F3)
        manager.on_key_down_event(event)
        scene.on_key_down_event.assert_called_once_with(event)
        assert manager.debug_overlay.is_visible is False

    def test_f4_reaches_a_focused_sprite_and_does_not_cycle(self, manager, scene):
        """Test F4 is forwarded while a sprite has keyboard focus."""
        scene.all_sprites.append(types.SimpleNamespace(is_active=True))
        event = key_down(pygame.K_F4)
        manager.on_key_down_event(event)
        scene.on_key_down_event.assert_called_once_with(event)
        assert manager.debug_overlay.panel is DebugPanel.ALL

    def test_unfocused_sprites_do_not_block_f3(self, manager, scene):
        """Test sprites without focus (or without is_active) do not block the toggle."""
        scene.all_sprites.extend([types.SimpleNamespace(is_active=False), types.SimpleNamespace()])
        manager.on_key_down_event(key_down(pygame.K_F3))
        assert manager.debug_overlay.is_visible is True

    def test_without_an_active_scene_other_keys_go_to_the_game_engine(self, manager, mocker):
        """Test the old proxy fallback survives: no scene means the game engine gets the event."""
        manager.active_scene = None
        engine = mocker.Mock()
        manager._game_engine = engine
        event = key_down(pygame.K_a)
        manager.on_key_down_event(event)
        engine.on_key_down_event.assert_called_once_with(event)

    def test_f3_without_an_active_scene_still_toggles(self, manager):
        """Test the overlay keys work with no active scene (nothing can have focus)."""
        manager.active_scene = None
        manager.on_key_down_event(key_down(pygame.K_F3))
        assert manager.debug_overlay.is_visible is True


class TestFrameHistory:
    """Frame times are recorded each frame."""

    def test_update_frame_services_records_dt(self, manager, mocker):
        """Test _update_frame_services records the frame time in the overlay."""
        spy = mocker.spy(manager.debug_overlay, 'record_frame')
        manager.dt = 0.0125
        manager._update_frame_services()
        spy.assert_called_once_with(frame_seconds=0.0125)
        assert manager.debug_overlay.frame_times() == [0.0125]


class TestPresentation:
    """What is on the display at flip time, and what is left on the surface after."""

    def test_visible_overlay_is_drawn_for_the_flip_only(self, manager, mocker):
        """Test the flip sees overlay pixels, and the surface is clean again afterwards."""
        clean_pixels = pixels_of(manager.screen)
        snapshots = capture_at_flip(mocker, manager)
        manager.debug_overlay.is_visible = True
        manager._present_frame(full_update=False)
        assert len(snapshots) == 1
        assert snapshots[0] != clean_pixels
        assert pixels_of(manager.screen) == clean_pixels

    def test_overlay_is_not_in_screenshots(self, manager, mocker):
        """Test a capture taken after presenting has no overlay pixels."""
        clean_pixels = pixels_of(manager.screen)
        capture_at_flip(mocker, manager)
        manager.debug_overlay.is_visible = True
        manager._present_frame(full_update=False)
        assert pixels_of(manager.screen.copy()) == clean_pixels

    def test_draw_receives_frame_information(self, manager, mocker):
        """Test draw is called with the scene, the pixel offset and a DebugFrameInfo."""
        capture_at_flip(mocker, manager)
        manager.target_fps = 60.44
        draw = mocker.patch.object(manager.debug_overlay, 'draw')
        manager.debug_overlay.is_visible = True
        manager._present_frame(full_update=False)
        draw.assert_called_once()
        assert draw.call_args.args == (manager.screen,)
        keyword_arguments = draw.call_args.kwargs
        assert keyword_arguments['scene'] is manager.active_scene
        assert keyword_arguments['screen_offset'] == (0, 0)
        frame_info = keyword_arguments['frame_info']
        assert isinstance(frame_info, DebugFrameInfo)
        assert frame_info.target_fps == 60.44
        assert frame_info.live_voice_count is None
        assert frame_info.screen_shake_offset == (0.0, 0.0)

    def test_hidden_overlay_does_not_draw_and_uses_the_update_path(self, manager, mocker):
        """Test a hidden overlay costs nothing: no draw, configured display update."""
        draw = mocker.patch.object(DebugOverlay, 'draw')
        flip = mocker.patch('pygame.display.flip')
        update_display = mocker.patch.object(manager, '_update_display')
        manager._present_frame(full_update=False)
        draw.assert_not_called()
        flip.assert_not_called()
        update_display.assert_called_once_with()

    def test_visible_overlay_without_an_active_scene_does_not_draw(self, manager, mocker):
        """Test there is nothing to draw with no scene, but the frame is still presented."""
        manager.active_scene = None
        draw = mocker.patch.object(DebugOverlay, 'draw')
        flip = mocker.patch('pygame.display.flip')
        manager.debug_overlay.is_visible = True
        manager._present_frame(full_update=False)
        draw.assert_not_called()
        flip.assert_called_once_with()

    def test_hiding_the_overlay_forces_one_full_flip(self, manager, mocker):
        """Test the next present after hiding is a full flip, then updates resume."""
        capture_at_flip(mocker, manager)
        manager.debug_overlay.is_visible = True
        manager._present_frame(full_update=False)
        manager.debug_overlay.is_visible = False

        flip = mocker.patch('pygame.display.flip')
        update_display = mocker.patch.object(manager, '_update_display')
        manager._present_frame(full_update=False)
        flip.assert_called_once_with()
        update_display.assert_not_called()

        manager._present_frame(full_update=False)
        flip.assert_called_once_with()
        update_display.assert_called_once_with()

    def test_screen_shake_shifts_the_frame_and_the_overlay_offset(self, manager, mocker):
        """Test a SCREEN shake shifts the flipped frame, passes its offset, and restores."""
        clean_pixels = pixels_of(manager.screen)
        mocker.patch.object(
            type(manager.screen_shake),
            'offset',
            new_callable=mocker.PropertyMock,
            return_value=SHAKE_OFFSET,
        )
        snapshots = capture_at_flip(mocker, manager)
        draw = mocker.patch.object(manager.debug_overlay, 'draw')
        manager.debug_overlay.is_visible = True
        manager._present_frame(full_update=False)

        assert draw.call_args.kwargs['screen_offset'] == (0, 4)
        assert draw.call_args.kwargs['frame_info'].screen_shake_offset == SHAKE_OFFSET
        shifted = pygame.Surface(SCREEN_SIZE)
        shifted.blit(manager.screen, (0, 4))
        assert snapshots[0] == pixels_of(shifted)
        assert snapshots[0] != clean_pixels
        assert pixels_of(manager.screen) == clean_pixels

    def test_overlay_draws_after_the_shift(self, manager, mocker):
        """Test the HUD marker stays put while the clean content shifts with the SCREEN shake."""
        hud_marker_position = (40, 5)
        mocker.patch.object(
            type(manager.screen_shake),
            'offset',
            new_callable=mocker.PropertyMock,
            return_value=SHAKE_OFFSET,
        )
        snapshots = capture_at_flip(mocker, manager)
        draw = mocker.patch.object(
            manager.debug_overlay,
            'draw',
            side_effect=lambda surface, **_: surface.set_at(hud_marker_position, MARKER_COLOR),
        )
        manager.debug_overlay.is_visible = True
        manager._present_frame(full_update=False)

        assert draw.call_args.kwargs['screen_offset'] == (0, 4)
        flipped = pygame.image.frombytes(snapshots[0], SCREEN_SIZE, 'RGB')
        assert tuple(flipped.get_at(hud_marker_position))[:3] == MARKER_COLOR
        shifted_content = (MARKER_POSITION[0], MARKER_POSITION[1] + 4)
        assert tuple(flipped.get_at(shifted_content))[:3] == MARKER_COLOR
        assert tuple(flipped.get_at(MARKER_POSITION))[:3] == BACKGROUND_COLOR

    def test_full_update_with_overlay_draws_and_restores(self, manager, mocker):
        """Test a full_update present also overlays for the flip and restores the clean frame."""
        clean_pixels = pixels_of(manager.screen)
        snapshots = capture_at_flip(mocker, manager)
        manager.debug_overlay.is_visible = True
        manager._present_frame(full_update=True)
        assert len(snapshots) == 1
        assert snapshots[0] != clean_pixels
        assert pixels_of(manager.screen) == clean_pixels

    def test_ending_shake_forces_one_full_flip(self, manager, mocker):
        """Test the present after a shake ends is one full flip, then updates resume."""
        offset = mocker.patch.object(
            type(manager.screen_shake),
            'offset',
            new_callable=mocker.PropertyMock,
            return_value=SHAKE_OFFSET,
        )
        capture_at_flip(mocker, manager)
        manager._present_frame(full_update=False)
        offset.return_value = (0.0, 0.0)

        flip = mocker.patch('pygame.display.flip')
        update_display = mocker.patch.object(manager, '_update_display')
        manager._present_frame(full_update=False)
        flip.assert_called_once_with()
        update_display.assert_not_called()
        manager._present_frame(full_update=False)
        flip.assert_called_once_with()
        update_display.assert_called_once_with()


class TestMissingKeyHandler:
    """The key-down fallback when nothing can handle the event."""

    def test_raises_when_neither_scene_nor_engine_has_a_handler(self, manager):
        """Test the old proxy's AttributeError survives with no scene and no game engine."""
        manager.active_scene = None
        manager._game_engine = None
        with pytest.raises(AttributeError, match='on_key_down_event'):
            manager.on_key_down_event(key_down(pygame.K_a))


class TestPausedSceneInspection:
    """The overlay inspects the paused gameplay scene, not the pause screen showing it."""

    def test_scene_inspects_itself_by_default(self):
        """A plain Scene's debug_subject is the scene itself."""
        plain_scene = Scene(options={})
        assert plain_scene.debug_subject is plain_scene

    def test_pause_scene_inspects_the_scene_it_paused(self, mocker):
        """After setup, PauseScene.debug_subject is the scene that was active before the pause."""
        pygame.display.set_mode(SCREEN_SIZE)
        SceneManager._reset()
        scene_manager = SceneManager()
        gameplay_scene = Scene(options={})
        scene_manager.previous_scene = gameplay_scene
        scene_manager.game_engine = mocker.Mock(
            OPTIONS={
                'update_type': 'dirty',
                'fps_refresh_rate': 1,
                'target_fps': 60,
                'fps_log_interval_ms': 1000.0,
            }
        )
        mocker.patch(
            'glitchygames.scenes.builtin_scenes.pause_scene.PauseOverlay',
            return_value=pygame.sprite.DirtySprite(),
        )
        pause_scene = PauseScene(options={})
        assert pause_scene.debug_subject is pause_scene  # nothing paused yet
        pause_scene.setup()
        assert pause_scene.debug_subject is gameplay_scene
        SceneManager._reset()

    def test_draw_receives_the_debug_subject_and_a_label(self, manager, scene, mocker):
        """A pause-like active scene hands the overlay its subject and names it in frame_info."""
        capture_at_flip(mocker, manager)
        paused_gameplay = types.SimpleNamespace(
            camera=Camera2D(*SCREEN_SIZE), all_sprites=[], NAME='Clockwork Keep'
        )
        scene.debug_subject = paused_gameplay
        draw = mocker.patch.object(manager.debug_overlay, 'draw')
        manager.debug_overlay.is_visible = True
        manager._present_frame(full_update=False)
        assert draw.call_args.kwargs['scene'] is paused_gameplay
        assert draw.call_args.kwargs['frame_info'].inspected_scene_label == 'Clockwork Keep'

    def test_no_label_when_the_active_scene_inspects_itself(self, manager, mocker):
        """frame_info carries no label for an ordinary scene."""
        capture_at_flip(mocker, manager)
        draw = mocker.patch.object(manager.debug_overlay, 'draw')
        manager.debug_overlay.is_visible = True
        manager._present_frame(full_update=False)
        assert draw.call_args.kwargs['scene'] is manager.active_scene
        assert draw.call_args.kwargs['frame_info'].inspected_scene_label is None
