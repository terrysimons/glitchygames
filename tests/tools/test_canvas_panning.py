#!/usr/bin/env python3
"""Tests for canvas panning functionality."""

from pathlib import Path

import pygame
import pytest

from glitchygames.bitmappy.editor import AnimatedCanvasSprite, BitmapEditorScene
from tests.mocks.test_mock_factory import MockFactory, MockSpriteConfig


class TestCanvasPanning:
    """Test cases for canvas panning functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Initialize pygame for testing
        pygame.init()

        # Create a display surface for testing
        pygame.display.set_mode((800, 600))

        # Use centralized mock factory
        self.animated_sprite = MockFactory.create_animated_sprite_mock(
            config=MockSpriteConfig(
                animation_name='test_animation',
                frame_size=(8, 8),
                pixel_color=(255, 0, 0),
                current_frame=0,
            ),
        )

        # Create canvas sprite
        self.canvas = AnimatedCanvasSprite(
            animated_sprite=self.animated_sprite,
            pixels_across=8,
            pixels_tall=8,
            pixel_width=16,
            pixel_height=16,
        )

    def teardown_method(self):
        """Clean up after tests."""
        pygame.quit()

    def test_panning_initialization(self):
        """Test that panning system is properly initialized."""
        # Check that frame-specific panning attributes exist
        assert hasattr(self.canvas, '_frame_panning')
        assert isinstance(self.canvas._frame_panning, dict)
        assert len(self.canvas._frame_panning) == 0  # No frames panned yet

    def test_pan_canvas_basic(self):
        """Test basic canvas panning functionality."""
        frame_key = self.canvas._get_current_frame_key()

        # Test panning right
        self.canvas.pan_canvas(1, 0)
        assert frame_key in self.canvas._frame_panning
        assert self.canvas._frame_panning[frame_key]['pan_x'] == 1
        assert self.canvas._frame_panning[frame_key]['pan_y'] == 0
        assert self.canvas._frame_panning[frame_key]['active'] is True

        # Test panning down
        self.canvas.pan_canvas(0, 1)
        assert self.canvas._frame_panning[frame_key]['pan_x'] == 1
        assert self.canvas._frame_panning[frame_key]['pan_y'] == 1

        # Test panning left
        self.canvas.pan_canvas(-1, 0)
        assert self.canvas._frame_panning[frame_key]['pan_x'] == 0
        assert self.canvas._frame_panning[frame_key]['pan_y'] == 1

        # Test panning up
        self.canvas.pan_canvas(0, -1)
        assert self.canvas._frame_panning[frame_key]['pan_x'] == 0
        assert self.canvas._frame_panning[frame_key]['pan_y'] == 0

    def test_pan_canvas_bounds_checking(self):
        """Test that panning respects bounds."""
        frame_key = self.canvas._get_current_frame_key()

        # Test panning beyond maximum bounds
        self.canvas.pan_canvas(15, 0)  # Beyond max_pan (10)
        assert frame_key not in self.canvas._frame_panning  # Should not create entry

        # Test panning within bounds
        self.canvas.pan_canvas(5, 0)
        assert frame_key in self.canvas._frame_panning
        assert self.canvas._frame_panning[frame_key]['pan_x'] == 5
        assert self.canvas._frame_panning[frame_key]['pan_y'] == 0

    def test_reset_panning(self):
        """Test resetting panning to original position."""
        frame_key = self.canvas._get_current_frame_key()

        # Pan the canvas
        self.canvas.pan_canvas(3, 2)
        assert self.canvas._frame_panning[frame_key]['active'] is True
        assert self.canvas._frame_panning[frame_key]['pan_x'] == 3
        assert self.canvas._frame_panning[frame_key]['pan_y'] == 2

        # Reset panning
        self.canvas.reset_panning()
        # Reset should clear the frame's panning state
        if frame_key in self.canvas._frame_panning:
            assert self.canvas._frame_panning[frame_key]['active'] is False
            assert self.canvas._frame_panning[frame_key]['pan_x'] == 0
            assert self.canvas._frame_panning[frame_key]['pan_y'] == 0

    def test_is_panning_active(self):
        """Test panning active state detection."""
        assert self.canvas.is_panning_active() is False

        self.canvas.pan_canvas(1, 0)
        assert self.canvas.is_panning_active() is True

        self.canvas.reset_panning()
        assert self.canvas.is_panning_active() is False

    def test_viewport_pixel_update(self):
        """Test that viewport pixels are updated correctly during panning."""
        frame_key = self.canvas._get_current_frame_key()

        # Pan the canvas
        self.canvas.pan_canvas(2, 1)

        # Check that frame panning state is created and pixels are updated
        assert frame_key in self.canvas._frame_panning
        assert self.canvas._frame_panning[frame_key]['original_pixels'] is not None
        assert len(self.canvas.pixels) == 64  # 8x8 viewport
        assert self.canvas.dirty_pixels == [True] * 64

    def test_panning_with_different_canvas_sizes(self):
        """Test panning with different canvas sizes."""
        # Test with larger canvas
        large_canvas = AnimatedCanvasSprite(
            animated_sprite=self.animated_sprite,
            pixels_across=16,
            pixels_tall=16,
            pixel_width=8,
            pixel_height=8,
        )

        # Test panning
        large_canvas.pan_canvas(5, 3)
        frame_key = large_canvas._get_current_frame_key()
        assert frame_key in large_canvas._frame_panning
        assert large_canvas._frame_panning[frame_key]['pan_x'] == 5
        assert large_canvas._frame_panning[frame_key]['pan_y'] == 3
        assert large_canvas.is_panning_active() is True

    def test_panning_state_persistence(self):
        """Test that panning state persists across operations."""
        # Pan the canvas
        self.canvas.pan_canvas(2, 1)
        assert self.canvas.is_panning_active() is True

        # Simulate some operations that shouldn't reset panning
        self.canvas.update()
        assert self.canvas.is_panning_active() is True

        # Only reset_panning should reset the state
        self.canvas.reset_panning()
        assert self.canvas.is_panning_active() is False


class TestPanningKeyboardHandling:
    """Test cases for keyboard handling of panning."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up test fixtures."""
        self._mocker = mocker
        pygame.init()

        # Create a display surface for testing
        pygame.display.set_mode((800, 600))

        # Use centralized mock factory for canvas
        self.canvas = MockFactory().create_canvas_mock(pixels_across=8, pixels_tall=8)
        self.canvas.pan_canvas = mocker.Mock()

        # Add necessary attributes for the commit test
        self.canvas.animated_sprite = mocker.Mock()
        mock_frame = mocker.Mock()
        mock_frame.pixels = [(255, 0, 0)] * 64
        animations_data = {'strip_1': [mock_frame]}
        self.canvas.animated_sprite._animations = animations_data
        self.canvas.animated_sprite.animations = animations_data
        self.canvas.animated_sprite._animation_order = ['strip_1']
        self.canvas.animated_sprite.animation_order = ['strip_1']
        self.canvas.current_animation = 'strip_1'
        self.canvas.current_frame = 0
        self.canvas.pixels = [(255, 0, 0)] * 64

        # Set up _frame_panning as a real dict on the mock canvas so
        # that _commit_panned_buffer can use 'in' operator on it
        self.canvas._frame_panning = {}
        self.canvas._get_current_frame_key = mocker.Mock(return_value='strip_1_0')

        # Create a mock scene with canvas
        self.scene = mocker.Mock(spec=BitmapEditorScene)
        self.scene.canvas = self.canvas

        # Create a real scene instance for testing keyboard handling
        # Use a smaller sprite to avoid layout issues
        mock_options = {'size': '32x32'}
        self.real_scene = BitmapEditorScene(mock_options)
        # Replace the canvas with our mock
        self.real_scene.canvas = self.canvas

        yield

        pygame.quit()

    def test_ctrl_shift_arrow_key_handling(self):
        """Test that Ctrl+Shift+Arrow keys trigger panning."""
        # Test Ctrl+Shift+Left
        event = self._mocker.Mock()
        event.key = pygame.K_LEFT
        event.mod = pygame.KMOD_CTRL | pygame.KMOD_SHIFT

        # Test the actual keyboard handling through the scene
        # LEFT arrow should pan left
        self.real_scene.on_key_down_event(event)
        self.canvas.pan_canvas.assert_called_with(-1, 0)

        # Test Ctrl+Shift+Right
        event.key = pygame.K_RIGHT
        self.canvas.pan_canvas.reset_mock()  # Reset the mock call history
        # RIGHT arrow should pan right
        self.real_scene.on_key_down_event(event)
        self.canvas.pan_canvas.assert_called_with(1, 0)

        # Test Ctrl+Shift+Up
        event.key = pygame.K_UP
        self.canvas.pan_canvas.reset_mock()
        # UP arrow should pan up
        self.real_scene.on_key_down_event(event)
        self.canvas.pan_canvas.assert_called_with(0, -1)

        # Test Ctrl+Shift+Down
        event.key = pygame.K_DOWN
        self.canvas.pan_canvas.reset_mock()
        # DOWN arrow should pan down
        self.real_scene.on_key_down_event(event)
        self.canvas.pan_canvas.assert_called_with(0, 1)

    def test_arrow_keys_without_ctrl_shift(self, mocker):
        """Test that arrow keys without Ctrl+Shift don't trigger panning."""
        # Test Left without Ctrl+Shift
        event = self._mocker.Mock()
        event.key = pygame.K_LEFT
        event.mod = 0  # No modifier keys

        mocker.patch.object(self.real_scene, 'canvas', self.canvas)
        self.real_scene.on_key_down_event(event)
        # Should not call pan_canvas
        self.canvas.pan_canvas.assert_not_called()

        # Test Left with only Ctrl (no Shift)
        event.mod = pygame.KMOD_CTRL
        mocker.patch.object(self.real_scene, 'canvas', self.canvas)
        self.real_scene.on_key_down_event(event)
        # Should not call pan_canvas
        self.canvas.pan_canvas.assert_not_called()

        # Test Left with only Shift (no Ctrl)
        event.mod = pygame.KMOD_SHIFT
        mocker.patch.object(self.real_scene, 'canvas', self.canvas)
        self.real_scene.on_key_down_event(event)
        # Should not call pan_canvas
        self.canvas.pan_canvas.assert_not_called()

    def test_panning_handler_method(self):
        """Test the panning handler method."""
        # Test with valid delta values
        self.real_scene._frame_operations.handle_canvas_panning(delta_x=1, delta_y=0)
        self.canvas.pan_canvas.assert_called_with(1, 0)

        # Test with negative delta values
        self.real_scene._frame_operations.handle_canvas_panning(delta_x=-1, delta_y=-1)
        self.canvas.pan_canvas.assert_called_with(-1, -1)

    def test_panning_handler_without_canvas(self):
        """Test panning handler when no canvas is available."""
        # Remove canvas
        self.real_scene.canvas = None

        # Should not raise an error
        self.real_scene._frame_operations.handle_canvas_panning(delta_x=1, delta_y=0)

    def test_key_release_commits_panned_buffer(self):
        """Test that releasing Ctrl+Shift+Arrow commits the panned buffer."""
        # First, pan the canvas
        event_down = self._mocker.Mock()
        event_down.key = pygame.K_LEFT
        event_down.mod = pygame.KMOD_CTRL | pygame.KMOD_SHIFT

        self.real_scene.on_key_down_event(event_down)
        self.canvas.pan_canvas.assert_called_with(-1, 0)

        # Simulate that panning is active by setting up _frame_panning state
        frame_key = 'strip_1_0'
        self.canvas._frame_panning[frame_key] = {
            'pan_x': -1,
            'pan_y': 0,
            'original_pixels': [(255, 0, 0)] * 64,
            'active': True,
        }

        # Now release the key
        event_up = self._mocker.Mock()
        event_up.key = pygame.K_LEFT
        event_up.mod = pygame.KMOD_CTRL | pygame.KMOD_SHIFT

        self.real_scene.on_key_up_event(event_up)

        # Verify that panning state was preserved (not cleared)
        assert frame_key in self.canvas._frame_panning
        frame_state = self.canvas._frame_panning[frame_key]
        assert frame_state['active'] is True
        assert frame_state['pan_x'] == -1
        assert frame_state['pan_y'] == 0
        assert frame_state['original_pixels'] is not None

    def test_key_release_updates_film_strip(self, mocker):
        """Test that releasing Ctrl+Shift+Arrow updates the film strip."""
        # First, pan the canvas
        event_down = self._mocker.Mock()
        event_down.key = pygame.K_LEFT
        event_down.mod = pygame.KMOD_CTRL | pygame.KMOD_SHIFT

        self.real_scene.on_key_down_event(event_down)
        self.canvas.pan_canvas.assert_called_with(-1, 0)

        # Simulate that panning is active by setting up _frame_panning state
        frame_key = 'strip_1_0'
        self.canvas._frame_panning[frame_key] = {
            'pan_x': -1,
            'pan_y': 0,
            'original_pixels': [(255, 0, 0)] * 64,
            'active': True,
        }

        # Mock the _update_film_strips_for_animated_sprite_update method
        mock_update_film = mocker.patch.object(
            self.real_scene.film_strip_coordinator,
            'update_film_strips_for_animated_sprite_update',
        )
        # Now release the key
        event_up = self._mocker.Mock()
        event_up.key = pygame.K_LEFT
        event_up.mod = pygame.KMOD_CTRL | pygame.KMOD_SHIFT

        self.real_scene.on_key_up_event(event_up)

        # Verify that film strip was updated
        mock_update_film.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])


class TestStaticSaveKeepsSpriteMetadata:
    """The canvas single-frame save keeps transitions, name, frame_anchor and hitbox."""

    def setup_method(self):
        """Create a canvas around a mock sprite (as TestCanvasPanning does)."""
        pygame.init()
        pygame.display.set_mode((800, 600))
        self.canvas = AnimatedCanvasSprite(
            animated_sprite=MockFactory.create_animated_sprite_mock(
                config=MockSpriteConfig(
                    animation_name='test_animation',
                    frame_size=(8, 8),
                    pixel_color=(255, 0, 0),
                    current_frame=0,
                ),
            ),
            pixels_across=8,
            pixels_tall=8,
            pixel_width=16,
            pixel_height=16,
        )

    def teardown_method(self):
        """Clean up after tests."""
        pygame.quit()

    def test_static_save_keeps_transitions(self, tmp_path):
        """The canvas's single-frame save path keeps the sprite's transitions."""
        import tomllib

        from glitchygames.sprites import AnimatedSprite

        sprite_file = tmp_path / 'single.toml'
        sprite_file.write_text(
            '[sprite]\nname = "single"\n\n'
            '[[animation]]\nnamespace = "idle"\nframe_interval = 0.15\n\n'
            '[[animation.frame]]\nnamespace = "idle"\nframe_index = 0\n'
            'pixels = """\n##\n##\n"""\n\n'
            '[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n\n'
            '[[transition]]\nfrom = "idle"\nto = "idle"\nwhen = "timer > 1.0"\n',
            encoding='utf-8',
        )
        self.canvas.animated_sprite = AnimatedSprite(str(sprite_file))
        saved_file = tmp_path / 'static.toml'

        self.canvas._save_as_static_sprite(str(saved_file), 'toml')

        saved_transitions = tomllib.loads(saved_file.read_text(encoding='utf-8'))['transition']
        assert saved_transitions == [{'from': 'idle', 'to': 'idle', 'when': 'timer > 1.0'}]

    def test_static_save_keeps_the_sprite_name(self, tmp_path):
        """battle_axe saved through the canvas's single-frame path keeps its name and glyphs."""
        import tomllib

        from glitchygames.sprites import AnimatedSprite

        source_file = Path('glitchygames/examples/resources/sprites/battle_axe.toml')
        self.canvas.animated_sprite = AnimatedSprite(str(source_file))
        saved_file = tmp_path / 'battle_axe.toml'

        self.canvas._save_as_static_sprite(str(saved_file), 'toml')

        original_data = tomllib.loads(source_file.read_text(encoding='utf-8'))
        saved_data = tomllib.loads(saved_file.read_text(encoding='utf-8'))
        assert saved_data['sprite']['name'] == 'bttlaxe.get'
        assert saved_data['sprite']['pixels'] == original_data['sprite']['pixels']

    def test_static_save_keeps_frame_anchor_and_sprite_hitbox(self, tmp_path):
        """A sprite-level hitbox (not stored on the frame) and frame_anchor survive."""
        from glitchygames.sprites import AnimatedSprite, FrameAnchor

        sprite_file = tmp_path / 'anchored.toml'
        sprite_file.write_text(
            '[sprite]\nname = "anchored"\nframe_anchor = "bottom"\n\n'
            '[sprite.hitbox]\noffset_x = 0\noffset_y = 1\nwidth = 2\nheight = 1\n\n'
            '[[animation]]\nnamespace = "idle"\n\n'
            '[[animation.frame]]\nnamespace = "idle"\nframe_index = 0\n'
            'pixels = """\n..\n##\n"""\n\n'
            '[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n\n'
            '[colors."."]\nred = 255\ngreen = 0\nblue = 255\n',
            encoding='utf-8',
        )
        self.canvas.animated_sprite = AnimatedSprite(str(sprite_file))
        saved_file = tmp_path / 'static.toml'

        self.canvas._save_as_static_sprite(str(saved_file), 'toml')
        reloaded_sprite = AnimatedSprite(str(saved_file))

        assert reloaded_sprite.name == 'anchored'
        assert reloaded_sprite.frame_anchor is FrameAnchor.BOTTOM
        assert reloaded_sprite.default_hitbox == pygame.Rect(0, 1, 2, 1)
