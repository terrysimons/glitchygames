"""Centralized mock factory for test objects.

This module provides reusable mock factories for creating consistent test objects
across all test files, reducing code duplication and ensuring proper mock configuration.
"""

from typing import ClassVar
from unittest.mock import Mock, patch

import pygame
from glitchygames.events import unhandled_event
from glitchygames.sprites import AnimatedSprite

# Constants for magic values
MIN_ARGS_FOR_DIMENSIONS = 2
DEFAULT_SIZE = 32
MIN_ARGS_FOR_FGCOLOR = 2


class MockSurface(pygame.Surface):
    """Wrapper around pygame.Surface that provides mockable convert methods."""

    def __init__(self, *args, **kwargs):
        """Initialize MockSurface with pygame compatibility."""
        if not pygame.get_init():
            pygame.init()

        # Validate dimensions to prevent invalid surface creation
        if args:
            # Handle both pygame.Surface((width, height)) and pygame.Surface(width, height)
            min_args_for_tuple = 1
            min_args_for_separate = 2
            default_surface_size = 32
            if (len(args) >= min_args_for_tuple and isinstance(args[0], tuple)
                and len(args[0]) >= min_args_for_separate):
                # Case: pygame.Surface((width, height))
                width, height = args[0]
                # Allow 0x0 surfaces for testing empty surface scenarios
                if isinstance(width, int) and isinstance(height, int) and (width < 0 or height < 0):
                    args = ((default_surface_size, default_surface_size), *args[1:])
            elif len(args) >= min_args_for_separate:
                # Case: pygame.Surface(width, height)
                width, height = args[0], args[1]
                # Allow 0x0 surfaces for testing empty surface scenarios
                if isinstance(width, int) and isinstance(height, int) and (width < 0 or height < 0):
                    args = (default_surface_size, default_surface_size, *args[2:])

        # Initialize the parent pygame.Surface
        super().__init__(*args, **kwargs)
        self._surface = self  # For compatibility with existing code
        self._mock_path = "/mock/surface/path.png"  # Default mock path for PathLike protocol

    def convert(self, *args, **kwargs):
        """Mock convert method that returns self."""
        return self

    def convert_alpha(self, *args, **kwargs):
        """Mock convert_alpha method that returns self."""
        return self

    def blit(self, source, dest, area=None, special_flags=0):
        """Delegate blit to the parent surface."""
        # Handle MockSurface sources by extracting their real surface
        if hasattr(source, "_surface"):
            source = source._surface

        # If source is still a mock, create a real surface for it
        if (hasattr(source, "_spec_class") or
            str(type(source)).find("Mock") != -1 or
            str(type(source)).find("MockSurface") != -1):
            # Create a real pygame surface for the mock by calling the real constructor
            real_source = pygame.surface.Surface((32, 32))
            real_source.fill((255, 255, 255))  # White background
            source = real_source

        # Handle mock destination (position)
        if hasattr(dest, "_spec_class") or str(type(dest)).find("Mock") != -1:
            dest = (0, 0)

        return super().blit(source, dest, area, special_flags)

    def fill(self, color, rect=None, special_flags=0):
        """Delegate fill to the parent surface."""
        return super().fill(color, rect, special_flags)

    def copy(self):
        """Return a copy of this surface."""
        return self

    def set_at(self, pos, color):
        """Set pixel color at position."""
        return super().set_at(pos, color)

    def get_at(self, pos):
        """Get pixel color at position."""
        # Get the color from the parent surface and ensure it's a pygame.Color object
        color = super().get_at(pos)
        # If it's a tuple, convert it to pygame.Color
        if isinstance(color, tuple):
            return pygame.Color(*color)
        return color

    def get_pixel_data(self):
        """Get pixel data for this surface."""
        width, height = self.get_size()
        # Return different pixel data based on the surface content
        # This simulates different frame content
        return [(255, 0, 0)] * (width * height)  # Red pixels for testing

    def get_rect(self, **kwargs):
        """Get rect for this surface."""
        return super().get_rect(**kwargs)

    def __fspath__(self):
        """Implement PathLike protocol for MockSurface."""
        return self._mock_path


class MockFactory:
    """Factory class for creating properly configured mock objects."""

    # Cache for expensive mock objects to improve test performance
    _cached_sprites: ClassVar[dict] = {}
    _cached_scenes: ClassVar[dict] = {}
    _cached_frames: ClassVar[dict] = {}

    @staticmethod
    def _copy_mock_sprite(original_sprite: Mock) -> Mock:
        """Create a copy of a mock sprite to avoid test interference."""
        # Create a new Mock instead of deep copying to avoid infinite recursion
        new_sprite = Mock(spec=type(original_sprite))

        # Copy essential attributes manually to avoid circular references
        for attr_name in [
            "_animations", "current_animation", "current_frame", "is_playing", "_is_looping"
        ]:
            if hasattr(original_sprite, attr_name):
                setattr(new_sprite, attr_name, getattr(original_sprite, attr_name))

        # Copy methods
        for attr_name in dir(original_sprite):
            if not attr_name.startswith("_") and callable(getattr(original_sprite, attr_name)):
                setattr(new_sprite, attr_name, getattr(original_sprite, attr_name))

        return new_sprite

    @staticmethod
    def clear_cache():
        """Clear all cached mock objects for test isolation."""
        MockFactory._cached_sprites.clear()
        MockFactory._cached_scenes.clear()
        MockFactory._cached_frames.clear()

    @staticmethod
    def create_animated_sprite_mock(  # noqa: PLR0915
        animation_name: str = "idle",
        frame_size: tuple = (8, 8),
        pixel_color: tuple = (255, 0, 0),
        current_frame: int = 0,
        *,
        is_playing: bool = False,
        is_looping: bool = True,
        use_cache: bool = True  # noqa: FBT001, FBT002, ARG004  # noqa: ARG004
    ) -> Mock:
        """Create a properly configured AnimatedSprite mock.

        Args:
            animation_name: Name of the animation (default: "idle")
            frame_size: Size of the frame as (width, height) (default: (8, 8))
            pixel_color: RGB color tuple for pixels (default: (255, 0, 0))
            current_frame: Current frame index (default: 0)
            is_playing: Whether animation is playing (default: False)
            is_looping: Whether animation is looping (default: True)
            use_cache: Whether to use cached version for performance (default: True)

        Returns:
            Properly configured AnimatedSprite mock

        """
        # Skip caching to avoid deep copy issues with Mock objects
        # cache_key = (
        #     animation_name, frame_size, pixel_color, current_frame, is_playing, is_looping
        # )
        # if use_cache and cache_key in MockFactory._cached_sprites:
        #     cached_sprite = MockFactory._cached_sprites[cache_key]
        #     # Return a copy to avoid test interference
        #     return MockFactory._copy_mock_sprite(cached_sprite)

        # Create the mock sprite
        mock_sprite = Mock(spec=AnimatedSprite)

        # Create multiple frames for animation simulation
        num_frames = 5  # Simulate 5 different frames
        mock_frames = []

        for frame_idx in range(num_frames):
            mock_frame = Mock()
            mock_frame.get_size.return_value = frame_size
            mock_frame.get_width.return_value = frame_size[0]
            mock_frame.get_height.return_value = frame_size[1]

            # Create different pixel colors for each frame to simulate animation
            frame_color = (
                (pixel_color[0] + frame_idx * 20) % 256,
                (pixel_color[1] + frame_idx * 30) % 256,
                (pixel_color[2] + frame_idx * 40) % 256
            )
            pixel_count = frame_size[0] * frame_size[1]
            mock_frame.get_pixel_data.return_value = [frame_color] * pixel_count

            # Create frame image with proper methods
            mock_frame_image = Mock()
            mock_frame_image.get_width.return_value = frame_size[0]
            mock_frame_image.get_height.return_value = frame_size[1]
            mock_frame_image.get_size.return_value = frame_size
            mock_frame.image = mock_frame_image

            # Add frame_index for sequence testing
            mock_frame.frame_index = frame_idx

            # Add varied duration for timing testing (simulate different frame speeds)
            # Frame 0: 0.3s (fast), Frame 1: 0.7s (normal), Frame 2: 1.0s (slow), etc.
            mock_frame.duration = 0.3 + (frame_idx * 0.2)  # 0.3, 0.5, 0.7, 0.9, 1.1

            mock_frames.append(mock_frame)

        # Use the first frame as the default
        mock_frame = mock_frames[0]

        # Add pixels attribute for surface creation
        mock_frame.pixels = [pixel_color] * pixel_count

        # Create multiple animations for testing (including "timing_demo" that tests expect)
        mock_sprite._animations = {
            animation_name: mock_frames,
            "timing_demo": mock_frames,  # Add timing_demo animation for tests
            "idle": mock_frames  # Ensure idle is available
        }
        mock_sprite.current_animation = animation_name  # Set to the provided animation name
        mock_sprite.current_frame = current_frame  # Start with specified frame
        mock_sprite.is_playing = is_playing
        mock_sprite._is_looping = is_looping
        mock_sprite.name = "Tiley McTile Face"  # Default name for tests

        # Add essential sprite attributes
        mock_sprite.image = mock_frames[0].image
        # Create a proper rect with all required attributes
        rect = pygame.Rect(0, 0, frame_size[0], frame_size[1])
        rect.top = 0
        rect.bottom = frame_size[1]
        rect.left = 0
        rect.right = frame_size[0]
        mock_sprite.rect = rect
        mock_sprite.animations = mock_sprite._animations  # Use the full animations dict
        mock_sprite.dirty = 1  # Required for pygame.sprite.DirtySprite

        # Add frames attribute that canvas_interfaces.py expects
        mock_sprite.frames = mock_sprite._animations

        # Add missing methods and attributes for comprehensive testing
        def mock_play():
            mock_sprite.is_playing = True
        mock_sprite.play = mock_play

        def mock_pause():
            mock_sprite.is_playing = False
        mock_sprite.pause = mock_pause

        def mock_stop():
            mock_sprite.is_playing = False
            mock_sprite.current_frame = 0
        mock_sprite.stop = mock_stop

        def mock_set_animation(animation_name):
            mock_sprite.current_animation = animation_name
        mock_sprite.set_animation = mock_set_animation

        def mock_set_frame(frame_idx):
            mock_sprite.current_frame = frame_idx
            # Update the sprite's image and rect to match the current frame
            if (mock_sprite.current_animation in mock_sprite._animations and
                frame_idx < len(mock_sprite._animations[mock_sprite.current_animation])):
                current_frame = mock_sprite._animations[mock_sprite.current_animation][frame_idx]
                mock_sprite.image = current_frame.image
                # Create a new rect with proper attributes
                new_rect = pygame.Rect(0, 0, frame_size[0], frame_size[1])
                new_rect.top = 0
                new_rect.bottom = frame_size[1]
                new_rect.left = 0
                new_rect.right = frame_size[0]
                mock_sprite.rect = new_rect
        mock_sprite.set_frame = mock_set_frame

        def mock_get_pixel_data():
            # Return pixel data for the current frame
            current_anim = mock_sprite.current_animation
            current_frame = mock_sprite.current_frame
            if (current_anim in mock_sprite._animations and
                current_frame < len(mock_sprite._animations[current_anim])):
                frame = mock_sprite._animations[current_anim][current_frame]
                return frame.get_pixel_data()
            return [pixel_color] * pixel_count
        mock_sprite.get_pixel_data = mock_get_pixel_data

        # Also add a method to get pixel data for a specific frame
        def mock_get_frame_pixel_data(frame_idx):
            if (mock_sprite.current_animation in mock_sprite._animations and
                frame_idx < len(mock_sprite._animations[mock_sprite.current_animation])):
                frame = mock_sprite._animations[mock_sprite.current_animation][frame_idx]
                return frame.get_pixel_data()
            return [pixel_color] * pixel_count
        mock_sprite.get_frame_pixel_data = mock_get_frame_pixel_data

        def mock_add_animation(name, frames):
            mock_sprite._animations[name] = frames
        mock_sprite.add_animation = mock_add_animation

        def mock_remove_animation(name):
            if name in mock_sprite._animations:
                del mock_sprite._animations[name]
        mock_sprite.remove_animation = mock_remove_animation

        def mock_set_looping(looping):
            mock_sprite._is_looping = looping
        mock_sprite.set_looping = mock_set_looping

        def mock_clear_surface_cache():
            mock_sprite._surface_cache.clear()
        mock_sprite.clear_surface_cache = mock_clear_surface_cache

        def mock_add_frame_observer(observer):
            mock_sprite._frame_manager._observers.append(observer)
        mock_sprite.add_frame_observer = mock_add_frame_observer

        def mock_remove_frame_observer(observer):
            if observer in mock_sprite._frame_manager._observers:
                mock_sprite._frame_manager._observers.remove(observer)
        mock_sprite.remove_frame_observer = mock_remove_frame_observer

        # Add get_frame method with error handling
        def mock_get_frame(animation_name, frame_idx):
            if animation_name not in mock_sprite._animations:
                raise ValueError(f"Animation '{animation_name}' not found")
            if frame_idx < 0 or frame_idx >= len(mock_sprite._animations[animation_name]):
                raise IndexError(f"Frame index {frame_idx} out of range for animation '{animation_name}'")
            return mock_sprite._animations[animation_name][frame_idx]
        mock_sprite.get_frame = mock_get_frame

        # Add get_animation_metadata method
        def mock_get_animation_metadata(animation_name):
            if animation_name not in mock_sprite._animations:
                raise ValueError(f"Animation '{animation_name}' not found")
            frames = mock_sprite._animations[animation_name]
            return {
                "name": animation_name,
                "frame_count": len(frames),
                "total_duration": sum(frame.duration for frame in frames),
                "is_looping": mock_sprite._is_looping
            }
        mock_sprite.get_animation_metadata = mock_get_animation_metadata

        mock_sprite.get_current_surface = Mock(return_value=Mock())
        mock_sprite.save = Mock()
        mock_sprite.load = Mock()

        # Add missing attributes
        mock_sprite._surface_cache = {}
        mock_sprite._frame_manager = Mock()
        mock_sprite._frame_manager._observers = []
        mock_sprite._frame_manager.animated_sprite = mock_sprite
        
        # Add frame_manager with current_animation and current_frame properties
        mock_sprite.frame_manager = Mock()
        mock_sprite.frame_manager.current_animation = animation_name
        mock_sprite.frame_manager.current_frame = current_frame
        
        # Add animation_count property
        mock_sprite.animation_count = len(mock_frames)
        
        # Add current_animation_frame_count property
        mock_sprite.current_animation_frame_count = len(mock_frames)
        
        # Add current_animation_total_duration property
        total_duration = sum(frame.duration for frame in mock_frames)
        mock_sprite.current_animation_total_duration = total_duration
        
        # Add animation_names property
        mock_sprite.animation_names = list(mock_sprite._animations.keys())
        
        # Add frame_interval property (simulate timing)
        mock_sprite.frame_interval = 1.0  # Default 1 second interval

        # Skip caching to avoid deep copy issues with Mock objects
        # if use_cache:
        #     MockFactory._cached_sprites[cache_key] = mock_sprite

        return mock_sprite

    @staticmethod
    def create_optimized_scene_mock(
        pixels_across: int = 32,
        pixels_tall: int = 32,
        pixel_size: int = 16,
        use_cache: bool = True  # noqa: FBT001, FBT002, ARG004
    ) -> Mock:
        """Create an optimized scene mock with caching for performance.

        Args:
            pixels_across: Width in pixels (default: 32)
            pixels_tall: Height in pixels (default: 32)
            pixel_size: Size of each pixel (default: 16)
            use_cache: Whether to use cached version (default: True)

        Returns:
            Optimized scene mock

        """
        # Skip caching to avoid deep copy issues with Mock objects
        # cache_key = (pixels_across, pixels_tall, pixel_size)
        # if use_cache and cache_key in MockFactory._cached_scenes:
        #     return MockFactory._copy_mock_sprite(MockFactory._cached_scenes[cache_key])

        # Create scene mock with minimal setup
        scene_mock = Mock()
        scene_mock.pixels_across = pixels_across
        scene_mock.pixels_tall = pixels_tall
        scene_mock.pixel_size = pixel_size

        # Create canvas mock
        canvas_mock = Mock()
        canvas_mock.rect = Mock()
        canvas_mock.rect.x = 0
        canvas_mock.rect.y = 24
        canvas_mock.rect.width = pixels_across * pixel_size
        canvas_mock.rect.height = pixels_tall * pixel_size
        canvas_mock.rect.right = canvas_mock.rect.x + canvas_mock.rect.width

        scene_mock.canvas = canvas_mock

        # Skip caching to avoid deep copy issues with Mock objects
        # if use_cache:
        #     MockFactory._cached_scenes[cache_key] = scene_mock

        return scene_mock

    @staticmethod
    def create_event_test_scene_mock(
        options: dict = None,
        event_handlers: dict = None,
        use_cache: bool = True  # noqa: FBT001, FBT002, ARG004
    ) -> Mock:
        """Create a scene mock for event testing.

        Args:
            options: Dictionary of scene options (default: basic event options)
            event_handlers: Dictionary of event handler methods (default: empty)
            use_cache: Whether to use cached version (default: True)

        Returns:
            Scene mock configured for event testing

        """
        if options is None:
            options = {
                "debug_events": False,
                "no_unhandled_events": True  # Enable globally to catch unhandled events as bugs
            }

        # Create scene mock
        scene_mock = Mock()
        scene_mock.options = options
        scene_mock.audio_events_received = []
        scene_mock.controller_events_received = []
        scene_mock.mouse_events_received = []
        scene_mock.keyboard_events_received = []
        scene_mock.joystick_events_received = []
        scene_mock.drop_events_received = []
        scene_mock.game_events_received = []
        scene_mock.font_events_received = []
        scene_mock.window_events_received = []
        scene_mock.midi_events_received = []
        scene_mock.text_events_received = []  # Track text events
        scene_mock.touch_events_received = []  # Track touch events
        # For joystick complexity: track multiple devices
        scene_mock.joystick_devices = {}  # device_index -> joystick_proxy
        scene_mock.joystick_device_events = []  # device add/remove events

        # Add event handler methods if provided
        if event_handlers is not None:
            for event_name, handler in event_handlers.items():
                setattr(scene_mock, event_name, handler)

        # Add unhandled event fallback only if event_handlers is explicitly empty (not None)
        if event_handlers is not None and len(event_handlers) == 0:
            # Explicitly empty event_handlers - add unhandled_event fallback for stub testing
            def unhandled_event_fallback(event):
                unhandled_event(scene_mock, event)
            scene_mock.on_controller_axis_motion_event = unhandled_event_fallback
            scene_mock.on_audio_device_added_event = unhandled_event_fallback
            scene_mock.on_font_changed_event = unhandled_event_fallback
            scene_mock.on_quit_event = unhandled_event_fallback
            scene_mock.on_active_event = unhandled_event_fallback
            scene_mock.on_user_event = unhandled_event_fallback
            scene_mock.on_video_resize_event = unhandled_event_fallback
            scene_mock.on_game_event = unhandled_event_fallback
            scene_mock.on_menu_item_event = unhandled_event_fallback
            scene_mock.on_joy_axis_motion_event = unhandled_event_fallback
            scene_mock.on_joy_button_down_event = unhandled_event_fallback
            scene_mock.on_joy_button_up_event = unhandled_event_fallback
            scene_mock.on_joy_device_added_event = unhandled_event_fallback
            scene_mock.on_joy_device_removed_event = unhandled_event_fallback
            scene_mock.on_joy_hat_motion_event = unhandled_event_fallback
            scene_mock.on_joy_ball_motion_event = unhandled_event_fallback
            scene_mock.on_midi_in_event = unhandled_event_fallback
            scene_mock.on_midi_out_event = unhandled_event_fallback
            scene_mock.on_text_input_event = unhandled_event_fallback
            scene_mock.on_text_editing_event = unhandled_event_fallback
            scene_mock.on_render_device_reset_event = unhandled_event_fallback
            scene_mock.on_render_targets_reset_event = unhandled_event_fallback
            scene_mock.on_clipboard_update_event = unhandled_event_fallback
            scene_mock.on_locale_changed_event = unhandled_event_fallback
            scene_mock.on_app_did_enter_background_event = unhandled_event_fallback
            scene_mock.on_app_did_enter_foreground_event = unhandled_event_fallback
            scene_mock.on_app_will_enter_background_event = unhandled_event_fallback
            scene_mock.on_app_will_enter_foreground_event = unhandled_event_fallback
            scene_mock.on_app_low_memory_event = unhandled_event_fallback
            scene_mock.on_app_terminating_event = unhandled_event_fallback
        else:
            # Add default event handlers if not provided
            if event_handlers is None or "on_audio_device_added_event" not in event_handlers:
                def default_audio_handler(event):
                    scene_mock.audio_events_received.append(event)
                    return True
                scene_mock.on_audio_device_added_event = default_audio_handler

            if event_handlers is None or "on_controller_axis_motion_event" not in event_handlers:
                def default_controller_handler(event):
                    scene_mock.controller_events_received.append(event)
                    return True
                scene_mock.on_controller_axis_motion_event = default_controller_handler

            if event_handlers is None or "on_text_input_event" not in event_handlers:
                def default_text_input_handler(event):
                    scene_mock.text_events_received.append(event)
                    return True
                scene_mock.on_text_input_event = default_text_input_handler

            if event_handlers is None or "on_text_editing_event" not in event_handlers:
                def default_text_editing_handler(event):
                    scene_mock.text_events_received.append(event)
                    return True
                scene_mock.on_text_editing_event = default_text_editing_handler

            if event_handlers is None or "on_render_device_reset_event" not in event_handlers:
                def default_render_device_reset_handler(event):
                    scene_mock.game_events_received.append(("render_device_reset", event))
                scene_mock.on_render_device_reset_event = default_render_device_reset_handler

            if event_handlers is None or "on_render_targets_reset_event" not in event_handlers:
                def default_render_targets_reset_handler(event):
                    scene_mock.game_events_received.append(("render_targets_reset", event))
                scene_mock.on_render_targets_reset_event = default_render_targets_reset_handler

            if event_handlers is None or "on_app_did_enter_background_event" not in event_handlers:
                def default_app_did_enter_background_handler(event):
                    scene_mock.game_events_received.append(("app_did_enter_background", event))
                scene_mock.on_app_did_enter_background_event = default_app_did_enter_background_handler

            if (event_handlers is None or
                "on_app_did_enter_foreground_event" not in event_handlers):
                def default_app_did_enter_foreground_handler(event):
                    scene_mock.game_events_received.append(("app_did_enter_foreground", event))
                scene_mock.on_app_did_enter_foreground_event = default_app_did_enter_foreground_handler

            if (event_handlers is None or
                "on_app_will_enter_background_event" not in event_handlers):
                def default_app_will_enter_background_handler(event):
                    scene_mock.game_events_received.append(("app_will_enter_background", event))
                scene_mock.on_app_will_enter_background_event = default_app_will_enter_background_handler

            if (event_handlers is None or
                "on_app_will_enter_foreground_event" not in event_handlers):
                def default_app_will_enter_foreground_handler(event):
                    scene_mock.game_events_received.append(("app_will_enter_foreground", event))
                scene_mock.on_app_will_enter_foreground_event = default_app_will_enter_foreground_handler

            if event_handlers is None or "on_app_low_memory_event" not in event_handlers:
                def default_app_low_memory_handler(event):
                    scene_mock.game_events_received.append(("app_low_memory", event))
                scene_mock.on_app_low_memory_event = default_app_low_memory_handler

            if event_handlers is None or "on_app_terminating_event" not in event_handlers:
                def default_app_terminating_handler(event):
                    scene_mock.game_events_received.append(("app_terminating", event))
                scene_mock.on_app_terminating_event = default_app_terminating_handler

            if event_handlers is None or "on_clipboard_update_event" not in event_handlers:
                def default_clipboard_update_handler(event):
                    scene_mock.game_events_received.append(("clipboard_update", event))
                scene_mock.on_clipboard_update_event = default_clipboard_update_handler

            if event_handlers is None or "on_locale_changed_event" not in event_handlers:
                def default_locale_changed_handler(event):
                    scene_mock.game_events_received.append(("locale_changed", event))
                scene_mock.on_locale_changed_event = default_locale_changed_handler

        return scene_mock

    def create_canvas_mock(self, pixels_across: int = 32, pixels_tall: int = 32) -> Mock:
        """Create a properly configured canvas mock.

        Args:
            pixels_across: Width of the canvas in pixels (default: 32)
            pixels_tall: Height of the canvas in pixels (default: 32)

        Returns:
            Properly configured canvas mock

        """
        mock_canvas = Mock()

        # Set up canvas dimensions
        mock_canvas.pixels_across = pixels_across
        mock_canvas.pixels_tall = pixels_tall

        # Create a real pixel array with magenta background
        pixel_count = pixels_across * pixels_tall
        mock_canvas.pixels = [(255, 0, 255)] * pixel_count  # Magenta background
        mock_canvas.dirty_pixels = [True] * pixel_count

        # Set up canvas properties with real values
        mock_canvas.current_animation = ""
        mock_canvas.current_frame = 0
        mock_canvas.animated_sprite = None

        # Set up rect with real values
        mock_canvas.rect = Mock()
        mock_canvas.rect.x = 0
        mock_canvas.rect.y = 0
        mock_canvas.rect.width = pixels_across * 16  # pixel_size * pixels_across
        mock_canvas.rect.height = pixels_tall * 16   # pixel_size * pixels_tall
        mock_canvas.rect.right = mock_canvas.rect.x + mock_canvas.rect.width
        mock_canvas.rect.y = 0

        # Set up other canvas attributes that might be used in arithmetic
        mock_canvas.pixel_size = 16
        mock_canvas.background_color = (255, 0, 255)

        # Mock methods
        mock_canvas.show_frame = Mock()
        mock_canvas.force_redraw = Mock()
        mock_canvas.mark_dirty = Mock()

        return mock_canvas

    @staticmethod
    def create_sprite_frame_mock(
        size: tuple = (8, 8),
        pixel_color: tuple = (255, 0, 0)
    ) -> Mock:
        """Create a properly configured SpriteFrame mock.

        Args:
            size: Frame size as (width, height) (default: (8, 8))
            pixel_color: RGB color tuple for pixels (default: (255, 0, 0))

        Returns:
            Properly configured SpriteFrame mock

        """
        mock_frame = Mock()
        mock_frame.get_size.return_value = size
        pixel_count = size[0] * size[1]
        mock_frame.get_pixel_data.return_value = [pixel_color] * pixel_count

        # Create frame image with proper methods
        mock_frame_image = Mock()
        mock_frame_image.get_width.return_value = size[0]
        mock_frame_image.get_height.return_value = size[1]
        mock_frame_image.get_size.return_value = size
        mock_frame.image = mock_frame_image

        # Add duration attribute for animation timing
        mock_frame.duration = 1.0  # 1 second duration

        # Add pixels attribute for surface creation
        mock_frame.pixels = [pixel_color] * pixel_count

        return mock_frame

    @staticmethod
    def create_event_mock(file_path: str) -> Mock:
        """Create a mock event object for file loading.

        Args:
            file_path: Path to the file being loaded

        Returns:
            Mock event object with text attribute

        """
        mock_event = Mock()
        mock_event.text = file_path
        return mock_event

    @staticmethod
    def create_pygame_surface_mock(width: int = 8, height: int = 8):
        """Create a pygame.Surface-like mock suitable for Sprite tests."""
        # Use the MockSurface class that inherits from pygame.Surface
        # This ensures it's recognized as a pygame.Surface instance
        return MockSurface((width, height))

    @staticmethod
    def create_real_pygame_surface(width: int = 8, height: int = 8):
        """Create a real pygame.Surface for tests that need actual pygame functionality."""
        import pygame  # noqa: PLC0415
        # Initialize pygame if not already initialized
        if not pygame.get_init():
            pygame.init()
        return pygame.Surface((width, height))

    @staticmethod
    def create_pygame_font_mock():
        """Create a mock pygame font for testing."""
        mock_font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        mock_font.render = Mock(return_value=rendered_surface)
        mock_font.render_to = Mock(return_value=Mock())
        mock_font.get_linesize.return_value = 16
        mock_font.size = Mock(return_value=(100, 16))  # (width, height)
        return mock_font

    @staticmethod
    def create_pygame_event_mock():
        """Create a mock pygame event for testing."""
        mock_event = Mock()
        mock_event.type = 0
        mock_event.pos = (0, 0)
        mock_event.button = 1
        mock_event.key = 0
        mock_event.unicode = ""
        mock_event.text = ""
        return mock_event

    @staticmethod
    def create_pygame_key_mock(shift_pressed=False):
        """Create a mock pygame key state for testing.
        
        Args:
            shift_pressed (bool): Whether shift keys should be pressed
            
        Returns:
            Mock: A mock that returns a list of key states
        """
        mock_key_state = [False] * 512
        if shift_pressed:
            mock_key_state[304] = True  # pygame.K_LSHIFT
            mock_key_state[303] = True  # pygame.K_RSHIFT
        return mock_key_state

    @staticmethod
    def create_pygame_joystick_mock():
        """Create a mock pygame joystick for testing."""
        mock_joystick = Mock()
        mock_joystick.get_name.return_value = "Mock Joystick"
        mock_joystick.get_numaxes.return_value = 2
        mock_joystick.get_numbuttons.return_value = 8
        mock_joystick.get_numhats.return_value = 1
        mock_joystick.get_axis.return_value = 0.0
        mock_joystick.get_button.return_value = False
        mock_joystick.get_hat.return_value = (0, 0)
        return mock_joystick

    @staticmethod
    def create_pygame_sprite_group_mock():
        """Create a mock pygame sprite group for testing."""
        mock_group = Mock()
        mock_group.add = Mock()
        mock_group.remove = Mock()
        mock_group.draw = Mock()
        mock_group.update = Mock()
        mock_group.__iter__ = Mock(return_value=iter([]))
        mock_group.__len__ = Mock(return_value=0)
        mock_group.__contains__ = Mock(return_value=False)
        return mock_group

    @staticmethod
    def create_game_mock():
        """Create a mock game for testing."""
        mock_game = Mock()
        mock_game.NAME = "MockGame"
        mock_game.VERSION = "1.0"
        mock_game.args = Mock(return_value=Mock())
        return mock_game

    @staticmethod
    def create_joystick_manager_mock(joystick_count: int = 0) -> Mock:
        """Create a properly configured JoystickManager mock.

        Args:
            joystick_count: Number of joysticks to simulate (default: 0)

        Returns:
            Properly configured JoystickManager mock

        """
        mock_manager = Mock()
        # Create a dictionary of joystick proxies (empty by default)
        mock_joysticks = {}
        for i in range(joystick_count):
            mock_joystick_proxy = Mock()
            mock_joystick_proxy._id = i
            mock_joystick_proxy.get_name.return_value = f"Mock Joystick {i}"
            mock_joystick_proxy.get_numaxes.return_value = 4
            mock_joystick_proxy.get_numbuttons.return_value = 12
            mock_joystick_proxy.get_numhats.return_value = 1
            mock_joystick_proxy.get_numballs.return_value = 0
            mock_joysticks[i] = mock_joystick_proxy

        mock_manager.joysticks = mock_joysticks
        return mock_manager

    @staticmethod
    def create_pygame_surface_class_mock():
        """Create a pygame.Surface class mock that works with isinstance checks."""
        # Create a mock class that can be used with isinstance
        class MockSurfaceClass:
            def __init__(self, *args, **kwargs):
                # Extract dimensions from constructor arguments
                if len(args) >= 1:
                    if isinstance(args[0], (tuple, list)) and len(args[0]) >= MIN_ARGS_FOR_DIMENSIONS:  # noqa: E501
                        width, height = args[0][0], args[0][1]
                    elif len(args) >= MIN_ARGS_FOR_DIMENSIONS:
                        width, height = args[0], args[1]
                    else:
                        width, height = DEFAULT_SIZE, DEFAULT_SIZE  # Default size
                else:
                    width, height = 32, 32  # Default size

                # Return a properly configured surface mock with correct dimensions
                self._mock_surface = MockFactory.create_pygame_surface_mock(width, height)
                # Copy all attributes from the mock surface
                for attr in dir(self._mock_surface):
                    if not attr.startswith("_"):
                        setattr(self, attr, getattr(self._mock_surface, attr))

        # Make it look like a proper class
        MockSurfaceClass.__name__ = "Surface"
        MockSurfaceClass.__module__ = "pygame"

        # Store the class for isinstance checks
        MockFactory._surface_class = MockSurfaceClass

        return MockSurfaceClass

    @staticmethod
    def create_display_mock(width: int = 800, height: int = 600) -> MockSurface:
        """Create a mock for pygame.display.get_surface()."""
        # Create a MockSurface that behaves like a pygame.Surface
        screen = MockSurface((width, height))

        # Override methods to return expected values
        screen.get_width = Mock(return_value=width)
        screen.get_height = Mock(return_value=height)
        screen.get_size = Mock(return_value=(width, height))

        # Provide surface methods that Scene class calls
        screen.convert = Mock(return_value=screen)
        screen.convert_alpha = Mock(return_value=screen)
        screen.blit = Mock(return_value=None)
        screen.fill = Mock(return_value=None)
        screen.copy = Mock(return_value=screen)
        screen.set_at = Mock(return_value=None)
        screen.get_at = Mock(return_value=pygame.Color(0, 0, 0, 255))

        # Provide a minimal screen rect-like attributes used by paddles
        screen.left = 0
        screen.right = width
        screen.top = 0
        screen.bottom = height

        # Add get_rect method that returns a mock with center attribute
        rect_mock = Mock()
        rect_mock.center = (width // 2, height // 2)
        screen.get_rect = Mock(return_value=rect_mock)

        return screen

    @staticmethod
    def _mock_sprite_init(self, *args, **kwargs):  # noqa: PLW0211,ARG004,PLR0915
        """Mock Sprite.__init__ that handles pygame.display.get_surface() properly."""
        # Avoid referencing self in debug output to prevent __str__ access before attributes are set
        # Extract arguments from kwargs since that's how they're being passed
        x = kwargs.get("x", 0)
        y = kwargs.get("y", 0)
        width = kwargs.get("width", 32)
        height = kwargs.get("height", 32)
        name = kwargs.get("name", "")
        parent = kwargs.get("parent")
        groups = kwargs.get("groups")

        # Set essential identifiers early
        self.name = name
        self.parent = parent

        # BitmappySprite-specific attributes
        self.filename = kwargs.get("filename", "")
        self.focusable = kwargs.get("focusable", False)

        # Initialize pixel data attributes
        self.pixels = []
        self.pixels_across = width
        self.pixels_tall = height

        # Ensure proper inheritance by setting __class__ if needed
        # This helps with isinstance() checks in tests
        if hasattr(self, "__class__"):
            # Make sure the class hierarchy is preserved
            pass

        # Add private _text attribute for TextSprite (must be set early)
        self._text = ""

        # Add background_color attribute for TextSprite
        self.background_color = (0, 0, 0, 0)  # Transparent black by default

        # Add text_color attribute for TextSprite
        self.text_color = (255, 255, 255)  # White text by default

        # CRITICAL: Set up rect FIRST, before any operations that might access it
        self.rect = Mock()
        self.rect.x = x
        self.rect.y = y
        self.rect.width = width
        self.rect.height = height

        # Add pygame.Rect properties that are commonly accessed
        self.rect.midleft = (x, y + height // 2)
        self.rect.midright = (x + width, y + height // 2)
        self.rect.midtop = (x + width // 2, y)
        self.rect.midbottom = (x + width // 2, y + height)
        self.rect.center = (x + width // 2, y + height // 2)
        self.rect.topleft = (x, y)
        self.rect.topright = (x + width, y)
        self.rect.bottomleft = (x, y + height)
        self.rect.bottomright = (x + width, y + height)
        self.rect.centerx = x + width // 2
        self.rect.centery = y + height // 2
        self.rect.left = x
        self.rect.right = x + width
        self.rect.top = y
        self.rect.bottom = y + height

        # pygame sprites expect groups() to be a method, not a list
        self._groups_list = groups or []

        # For pygame.sprite.Sprite.add() calls, we need groups to be iterable
        # So we set it as a property that returns the list
        self._groups = self._groups_list

        # Create a groups method that returns the list - pygame expects groups() to be callable
        self.groups = lambda: self._groups_list

        # Add common UI component attributes that might be accessed
        # Note: TextSprite manages its own text property, so we don't set self.text here

        # For ButtonSprite, we need to ensure that when TextSprite is created, it has the right attributes  # noqa: E501
        # This will be handled by the TextSprite mock constructor

        # Add x and y properties for TextSprite compatibility
        self._x = x
        self._y = y

        # pygame sprites expect __g to be a set-like object with add method
        self.__g = set()

        # Establish dirty/visible flags BEFORE property setters use them
        self.dirty = 1
        self.visible = 1
        self._Sprite__dirty = 1
        self._Sprite__visible = 1

        # Add pygame sprite required attributes
        self.blendmode = 0  # pygame.BLEND_NORMAL

        # Now set basic attributes - use private attributes to avoid triggering property setters
        # that might reference attributes not yet initialized (e.g., ButtonSprite.x setter references self.text)  # noqa: E501
        self._x = x
        self._y = y
        self._width = width
        self._height = height

        # Mock screen with proper methods
        self.screen = MockFactory.create_display_mock()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        # Mock other sprite attributes
        self.image = Mock()

        # Debug logging removed to avoid accessing attributes prematurely

        # Also set the pygame sprite attributes that are needed
        self._Sprite__g = set()

    @staticmethod
    def create_pygame_display_mock() -> Mock:
        """Create a comprehensive pygame.display mock with initialization."""
        display_mock = Mock()
        display_mock.init.return_value = None
        display_mock.quit.return_value = None
        # Ensure quit doesn't actually quit the display
        display_mock.quit.side_effect = lambda: None

        # Create a single display surface mock that will be reused
        display_surface = MockFactory.create_display_mock()
        display_mock.get_surface.return_value = display_surface
        display_mock.set_mode.return_value = display_surface
        display_mock.flip.return_value = None
        display_mock.update.return_value = None
        display_mock.set_icon.return_value = None
        display_mock.get_caption.return_value = ("Test Game", "Test Game")

        # Add Info class to display mock
        class MockDisplayInfo:
            def __init__(self):
                self.current_w = 1280
                self.current_h = 720

        display_mock.Info = MockDisplayInfo
        return display_mock

    @staticmethod
    def setup_minimal_pygame_mocks():
        """Set up minimal pygame mocks that only mock the display surface.

        This is used for global mocks to prevent 'display Surface quit' errors
        while allowing other pygame objects to work normally.

        Returns:
            tuple: (display_patcher, display_get_surface_patcher)

        """
        # Create display mock
        display_mock = MockFactory.create_pygame_display_mock()
        display_surface = display_mock.get_surface.return_value

        # Only patch display-related functions
        display_patcher = patch("pygame.display", display_mock)
        display_get_surface_patcher = patch("pygame.display.get_surface", return_value=display_surface)

        return (display_patcher, display_get_surface_patcher)

    def setup_pygame_mocks():  # noqa: PLR0915,PLR0914
        """Set up comprehensive pygame mocks for testing.

        Returns:
            tuple: (display_patcher, surface_patcher, event_patcher, ...)

        """
        # Create comprehensive mocks
        display_mock = MockFactory.create_pygame_display_mock()

        # Get the display surface from the display mock to ensure consistency
        display_surface = display_mock.get_surface.return_value

        # Set up patches
        display_patcher = patch("pygame.display", display_mock)
        # Also patch pygame.display.get_surface directly to ensure it returns the same mock
        display_get_surface_patcher = patch("pygame.display.get_surface", return_value=display_surface)

        # Display info mock is now included in display_mock

        surface_class_mock = MockFactory.create_pygame_surface_class_mock()
        surface_patcher = patch("pygame.Surface", surface_class_mock)
        event_patcher = patch("pygame.event.get", return_value=[])
        event_blocked_patcher = patch("pygame.event.get_blocked", return_value=False)
        event_post_patcher = patch("pygame.event.post")
        event_event_patcher = patch("pygame.event.Event")

        # Additional pygame mocks for Film Strip and other modules
        draw_circle_patcher = patch("pygame.draw.circle")
        draw_line_patcher = patch("pygame.draw.line")
        draw_rect_patcher = patch("pygame.draw.rect")

        # Sprite group mocking - create proper mocks for LayeredDirty and other sprite groups
        def mock_layered_dirty_constructor(*args, **kwargs):
            """Mock pygame.sprite.LayeredDirty constructor that returns a working mock."""
            mock_group = Mock()
            mock_group._spritelist = []
            mock_group._old_rect = {}
            mock_group._clip = None

            def mock_draw(surface):
                """Mock draw method that handles sprites properly."""
                for sprite in mock_group._spritelist:
                    if hasattr(sprite, "image") and hasattr(sprite, "rect"):
                        # Update _old_rect to prevent TypeError
                        if sprite not in mock_group._old_rect:
                            mock_group._old_rect[sprite] = sprite.rect.copy()
                        # Draw the sprite
                        surface.blit(sprite.image, sprite.rect)

            def mock_add(*sprites):
                """Mock add method."""
                for sprite in sprites:
                    if sprite not in mock_group._spritelist:
                        mock_group._spritelist.append(sprite)
                        # Initialize _old_rect for the sprite
                        if hasattr(sprite, "rect"):
                            mock_group._old_rect[sprite] = sprite.rect.copy()

            def mock_remove(*sprites):
                """Mock remove method."""
                for sprite in sprites:
                    if sprite in mock_group._spritelist:
                        mock_group._spritelist.remove(sprite)
                    if sprite in mock_group._old_rect:
                        del mock_group._old_rect[sprite]

            mock_group.draw = mock_draw
            mock_group.add = mock_add
            mock_group.remove = mock_remove
            mock_group.__iter__ = lambda self: iter(mock_group._spritelist)
            mock_group.__len__ = lambda self: len(mock_group._spritelist)
            mock_group.__contains__ = lambda self, sprite: sprite in mock_group._spritelist

            return mock_group

        layered_dirty_patcher = patch("pygame.sprite.LayeredDirty", side_effect=mock_layered_dirty_constructor)
        sprite_group_patcher = patch("pygame.sprite.Group", side_effect=mock_layered_dirty_constructor)

        # Mock SpriteFactory.load_sprite to return our mocked animated sprite
        def mock_sprite_factory_load_sprite(*, filename: str = None):
            """Mock SpriteFactory.load_sprite to return a mocked animated sprite."""
            return MockFactory.create_animated_sprite_mock(
                animation_name="idle",
                frame_size=(8, 8),
                pixel_color=(255, 0, 0),
                current_frame=0,
                is_playing=True,
                is_looping=True
            )

        sprite_factory_patcher = patch("glitchygames.sprites.SpriteFactory.load_sprite", side_effect=mock_sprite_factory_load_sprite)

        # Draw function mocking - create mocks that handle MockSurface objects
        import pygame  # noqa: PLC0415
        original_draw_polygon = pygame.draw.polygon

        def mock_draw_polygon(surface, color, points, width=0):
            """Mock pygame.draw.polygon that handles MockSurface objects."""
            if hasattr(surface, "_surface"):
                # Use the original pygame.draw.polygon directly to avoid recursion
                return original_draw_polygon(surface._surface, color, points, width)
            return original_draw_polygon(surface, color, points, width)

        draw_polygon_patcher = patch("pygame.draw.polygon", side_effect=mock_draw_polygon)

        # Sound/mixer mocking
        mixer_mock = Mock()
        mixer_mock.Sound.return_value = Mock()
        mixer_mock.get_init.return_value = (22050, -16, 2)  # frequency, format, channels
        mixer_patcher = patch("pygame.mixer", mixer_mock)
        mixer_sound_patcher = patch("pygame.mixer.Sound", return_value=Mock())

        # Keyboard mocking
        key_mock = Mock()
        key_mock.set_repeat.return_value = None
        key_mock.get_mods.return_value = 0  # No modifier keys pressed by default
        key_mock.get_pressed.return_value = [False] * 512  # All keys not pressed by default
        key_patcher = patch("pygame.key", key_mock)

        # Transform mocking - create a mock that returns a real surface
        def mock_transform_scale(surface, size):
            """Mock pygame.transform.scale that returns a real surface."""
            import pygame  # noqa: PLC0415
            # Use surface to avoid unused argument warning
            _ = surface
            return pygame.Surface(size)
        transform_scale_patcher = patch("pygame.transform.scale", side_effect=mock_transform_scale)

        # Surface mocking - use the mock surface class instead of real surfaces
        # The surface_class_mock already handles this properly

        # FontManager mock - create a mock font that returns a proper surface
        mock_font = Mock()

        # Create a mock surface for text rendering that handles all render signatures
        def mock_render(*args, **kwargs):
            # Handle different render method signatures
            text = str(args[0]) if len(args) >= 1 else "Mock"

            # Create a real surface for text rendering
            import pygame  # noqa: PLC0415
            if not pygame.get_init():
                pygame.init()

            # Create a real surface with approximate text dimensions
            width = len(text) * 8  # Approximate text width
            height = 16  # Default height
            surface = pygame.Surface((width, height), pygame.SRCALPHA)
            surface.fill((0, 0, 0, 0))  # Transparent background

            # Create a real rect for the text
            text_rect = pygame.Rect(0, 0, width, height)
            surface.get_rect = Mock(return_value=text_rect)

            # Handle different return types (surface vs (surface, rect))
            if "fgcolor" in kwargs or len(args) >= MIN_ARGS_FOR_FGCOLOR:
                # pygame.freetype style - return (surface, rect)
                return surface, text_rect
            # pygame.font style - return surface
            return surface

        # Handle both render and render_to methods
        mock_font.render = mock_render
        mock_font.render_to = Mock(return_value=Mock())

        # Add other font methods that might be called
        mock_font.get_linesize.return_value = 16
        mock_font.size = Mock(return_value=(100, 16))  # (width, height)

        # Image module mock - create a mock for pygame.image.tostring
        def mock_image_tostring(surface, format_str):
            """Mock pygame.image.tostring that returns mock pixel data."""
            # Use format_str to avoid unused argument warning
            _ = format_str
            # Return mock pixel data based on surface size
            if hasattr(surface, "get_width") and hasattr(surface, "get_height"):
                width = surface.get_width()
                height = surface.get_height()

                # Check if this is a single-color surface (for legacy sprite tests)
                # If the surface has a single color, return consistent pixel data
                if hasattr(surface, "_test_single_color") and surface._test_single_color:
                    # Return all pixels as red (255, 0, 0) for single color tests
                    pixel_data = bytearray()
                    for _ in range(height):
                        for _ in range(width):
                            pixel_data.extend([255, 0, 0])  # Red color
                    return bytes(pixel_data)
                # Return mock RGB data with unique colors for testing
                # Create unique colors based on position to test color limits
                pixel_data = bytearray()
                for y in range(height):
                    for x in range(width):
                        # Create unique colors based on position
                        # Use a simple formula that ensures unique colors
                        r = (x + y * width) % 256
                        g = ((x + y * width) * 2) % 256
                        b = ((x + y * width) * 3) % 256
                        pixel_data.extend([r, g, b])
                return bytes(pixel_data)
            return b"\x00" * 100  # Default mock data
        image_tostring_patcher = patch("pygame.image.tostring", side_effect=mock_image_tostring)
        mock_font.get_linesize.return_value = 24  # Default line height
        mock_font.size = 24  # For freetype fonts
        font_manager_patcher = patch("glitchygames.fonts.FontManager.get_font", return_value=mock_font)  # noqa: E501

        # Enhanced pygame mocks for edge cases
        # Clock mocking
        clock_mock = Mock()
        clock_mock.tick.return_value = 16.67  # ~60 FPS
        clock_mock.get_fps.return_value = 60.0
        clock_patcher = patch("pygame.time.Clock", return_value=clock_mock)

        # Enhanced event mocking for specific edge cases
        event_post_mock = Mock()
        event_event_mock = Mock()
        event_event_mock.return_value = Mock()  # Return a mock event object
        event_post_patcher = patch("pygame.event.post", event_post_mock)
        event_event_patcher = patch("pygame.event.Event", event_event_mock)

        # Sprite class mocking - patch the BitmappySprite constructor to handle pygame.display.get_surface()  # noqa: E501
        sprite_patcher = patch("glitchygames.sprites.BitmappySprite.__init__", MockFactory._mock_sprite_init)  # noqa: E501

        # Key constants mocking
        key_constants_patcher = patch("pygame.K_q", 113)
        key_escape_patcher = patch("pygame.K_ESCAPE", 27)
        key_lshift_patcher = patch("pygame.K_LSHIFT", 304)
        key_rshift_patcher = patch("pygame.K_RSHIFT", 303)
        key_down_patcher = patch("pygame.KEYDOWN", pygame.KEYDOWN)
        key_up_patcher = patch("pygame.KEYUP", pygame.KEYUP)
        mouse_button_down_patcher = patch("pygame.MOUSEBUTTONDOWN", pygame.MOUSEBUTTONDOWN)
        mouse_button_up_patcher = patch("pygame.MOUSEBUTTONUP", pygame.MOUSEBUTTONUP)
        mouse_motion_patcher = patch("pygame.MOUSEMOTION", pygame.MOUSEMOTION)
        mouse_wheel_patcher = patch("pygame.MOUSEWHEEL", pygame.MOUSEWHEEL)
        quit_event_patcher = patch("pygame.QUIT", pygame.QUIT)
        text_input_patcher = patch("pygame.TEXTINPUT", pygame.TEXTINPUT)
        touch_down_patcher = patch("pygame.FINGERDOWN", pygame.FINGERDOWN)
        touch_up_patcher = patch("pygame.FINGERUP", pygame.FINGERUP)
        touch_motion_patcher = patch("pygame.FINGERMOTION", pygame.FINGERMOTION)
        window_resized_patcher = patch("pygame.WINDOWRESIZED", pygame.WINDOWRESIZED)
        window_restored_patcher = patch("pygame.WINDOWRESTORED", pygame.WINDOWRESTORED)
        window_focus_gained_patcher = patch("pygame.WINDOWFOCUSGAINED", pygame.WINDOWFOCUSGAINED)
        window_focus_lost_patcher = patch("pygame.WINDOWFOCUSLOST", pygame.WINDOWFOCUSLOST)
        # Use real pygame constants for audio events
        audio_device_added_patcher = patch("pygame.AUDIODEVICEADDED", pygame.AUDIODEVICEADDED)
        audio_device_removed_patcher = patch("pygame.AUDIODEVICEREMOVED", pygame.AUDIODEVICEREMOVED)

        # Joystick/Controller events
        joystick_axis_motion_patcher = patch("pygame.JOYAXISMOTION", pygame.JOYAXISMOTION)
        joystick_ball_motion_patcher = patch("pygame.JOYBALLMOTION", pygame.JOYBALLMOTION)
        joystick_button_down_patcher = patch("pygame.JOYBUTTONDOWN", pygame.JOYBUTTONDOWN)
        joystick_button_up_patcher = patch("pygame.JOYBUTTONUP", pygame.JOYBUTTONUP)
        joystick_hat_motion_patcher = patch("pygame.JOYHATMOTION", pygame.JOYHATMOTION)
        joystick_device_added_patcher = patch("pygame.JOYDEVICEADDED", pygame.JOYDEVICEADDED)
        joystick_device_removed_patcher = patch("pygame.JOYDEVICEREMOVED", pygame.JOYDEVICEREMOVED)

        # Controller events
        controller_axis_motion_patcher = patch("pygame.CONTROLLERAXISMOTION", pygame.CONTROLLERAXISMOTION)
        controller_button_down_patcher = patch("pygame.CONTROLLERBUTTONDOWN", pygame.CONTROLLERBUTTONDOWN)
        controller_button_up_patcher = patch("pygame.CONTROLLERBUTTONUP", pygame.CONTROLLERBUTTONUP)
        controller_device_added_patcher = patch("pygame.CONTROLLERDEVICEADDED", pygame.CONTROLLERDEVICEADDED)
        controller_device_removed_patcher = patch("pygame.CONTROLLERDEVICEREMOVED", pygame.CONTROLLERDEVICEREMOVED)
        controller_device_remapped_patcher = patch("pygame.CONTROLLERDEVICEREMAPPED", pygame.CONTROLLERDEVICEREMAPPED)

        # Drop events
        drop_begin_patcher = patch("pygame.DROPBEGIN", pygame.DROPBEGIN)
        drop_complete_patcher = patch("pygame.DROPCOMPLETE", pygame.DROPCOMPLETE)
        drop_file_patcher = patch("pygame.DROPFILE", pygame.DROPFILE)
        drop_text_patcher = patch("pygame.DROPTEXT", pygame.DROPTEXT)

        # MIDI events
        midi_in_patcher = patch("pygame.MIDIIN", pygame.MIDIIN)

        # User events
        user_event_patcher = patch("pygame.USEREVENT", pygame.USEREVENT)

        # Return patchers without starting them - let the test files start them

        return (display_patcher, display_get_surface_patcher, surface_patcher, event_patcher, event_blocked_patcher,  # noqa: E501
                event_post_patcher, event_event_patcher, draw_circle_patcher, draw_line_patcher,
                draw_rect_patcher, draw_polygon_patcher, layered_dirty_patcher, sprite_group_patcher, sprite_factory_patcher, mixer_patcher, mixer_sound_patcher, key_patcher, transform_scale_patcher, image_tostring_patcher, font_manager_patcher, clock_patcher,  # noqa: E501
                sprite_patcher, key_constants_patcher, key_escape_patcher, key_lshift_patcher, key_rshift_patcher, key_down_patcher, key_up_patcher,  # noqa: E501
                mouse_button_down_patcher, mouse_button_up_patcher, mouse_motion_patcher,
                mouse_wheel_patcher, quit_event_patcher, text_input_patcher, touch_down_patcher,
                touch_up_patcher, touch_motion_patcher, window_resized_patcher, window_restored_patcher,  # noqa: E501
                window_focus_gained_patcher, window_focus_lost_patcher, audio_device_added_patcher, audio_device_removed_patcher,  # noqa: E501
                joystick_axis_motion_patcher, joystick_ball_motion_patcher,  # noqa: E501
                joystick_button_down_patcher, joystick_button_up_patcher, joystick_hat_motion_patcher,  # noqa: E501
                joystick_device_added_patcher, joystick_device_removed_patcher, controller_axis_motion_patcher,  # noqa: E501
                controller_button_down_patcher, controller_button_up_patcher, controller_device_added_patcher,  # noqa: E501
                controller_device_removed_patcher, controller_device_remapped_patcher, drop_begin_patcher,  # noqa: E501
                drop_complete_patcher, drop_file_patcher, drop_text_patcher, midi_in_patcher, user_event_patcher)  # noqa: E501

    @staticmethod
    def teardown_pygame_mocks(patchers):  # noqa: PLR0915,PLR0914
        """Tear down pygame mocks to prevent test interference.

        Args:
            patchers: Tuple of patchers returned by setup_pygame_mocks()

        """
        (display_patcher, display_get_surface_patcher, surface_patcher, event_patcher, event_blocked_patcher,  # noqa: E501
         event_post_patcher, event_event_patcher, draw_circle_patcher, draw_line_patcher,
         draw_rect_patcher, draw_polygon_patcher, layered_dirty_patcher, sprite_group_patcher, sprite_factory_patcher, mixer_patcher, mixer_sound_patcher, key_patcher,  # noqa: E501
         transform_scale_patcher, image_tostring_patcher, font_manager_patcher, clock_patcher,  # noqa: E501
         sprite_patcher, key_constants_patcher, key_escape_patcher, key_lshift_patcher, key_rshift_patcher, key_down_patcher, key_up_patcher,  # noqa: E501
         mouse_button_down_patcher, mouse_button_up_patcher, mouse_motion_patcher,
         mouse_wheel_patcher, quit_event_patcher, text_input_patcher, touch_down_patcher,
         touch_up_patcher, touch_motion_patcher, window_resized_patcher, window_restored_patcher,
         window_focus_gained_patcher, window_focus_lost_patcher, audio_device_added_patcher, audio_device_removed_patcher,
         joystick_axis_motion_patcher, joystick_ball_motion_patcher,
         joystick_button_down_patcher, joystick_button_up_patcher, joystick_hat_motion_patcher,
         joystick_device_added_patcher, joystick_device_removed_patcher, controller_axis_motion_patcher,  # noqa: E501
         controller_button_down_patcher, controller_button_up_patcher, controller_device_added_patcher,  # noqa: E501
         controller_device_removed_patcher, controller_device_remapped_patcher, drop_begin_patcher,
         drop_complete_patcher, drop_file_patcher, drop_text_patcher, midi_in_patcher, user_event_patcher) = patchers  # noqa: E501

        # Stop all patches
        display_patcher.stop()
        display_get_surface_patcher.stop()
        surface_patcher.stop()
        event_patcher.stop()
        event_blocked_patcher.stop()
        event_post_patcher.stop()
        event_event_patcher.stop()
        draw_circle_patcher.stop()
        draw_line_patcher.stop()
        draw_rect_patcher.stop()
        draw_polygon_patcher.stop()
        layered_dirty_patcher.stop()
        sprite_group_patcher.stop()
        sprite_factory_patcher.stop()
        key_patcher.stop()
        transform_scale_patcher.stop()
        font_manager_patcher.stop()
        clock_patcher.stop()
        sprite_patcher.stop()

        # Stop all constant patches
        key_constants_patcher.stop()
        key_escape_patcher.stop()
        key_lshift_patcher.stop()
        key_rshift_patcher.stop()
        key_down_patcher.stop()
        key_up_patcher.stop()
        mouse_button_down_patcher.stop()
        mouse_button_up_patcher.stop()
        mouse_motion_patcher.stop()
        mouse_wheel_patcher.stop()
        quit_event_patcher.stop()
        text_input_patcher.stop()
        touch_down_patcher.stop()
        touch_up_patcher.stop()
        touch_motion_patcher.stop()
        window_resized_patcher.stop()
        window_restored_patcher.stop()
        window_focus_gained_patcher.stop()
        window_focus_lost_patcher.stop()
        audio_device_added_patcher.stop()
        audio_device_removed_patcher.stop()
        joystick_axis_motion_patcher.stop()
        joystick_ball_motion_patcher.stop()
        joystick_button_down_patcher.stop()
        joystick_button_up_patcher.stop()
        joystick_hat_motion_patcher.stop()
        joystick_device_added_patcher.stop()
        joystick_device_removed_patcher.stop()
        controller_axis_motion_patcher.stop()
        controller_button_down_patcher.stop()
        controller_button_up_patcher.stop()
        controller_device_added_patcher.stop()
        controller_device_removed_patcher.stop()
        controller_device_remapped_patcher.stop()
        drop_begin_patcher.stop()
        drop_complete_patcher.stop()
        drop_file_patcher.stop()
        drop_text_patcher.stop()
        midi_in_patcher.stop()
        user_event_patcher.stop()


# Convenience functions for common use cases
def create_8x8_sprite_mock(animation_name: str = "idle") -> Mock:
    """Create a standard 8x8 sprite mock."""
    return MockFactory.create_animated_sprite_mock(
        animation_name=animation_name,
        frame_size=(8, 8)
    )


def create_10x10_sprite_mock(animation_name: str = "idle") -> Mock:
    """Create a 10x10 sprite mock for dimension testing."""
    return MockFactory.create_animated_sprite_mock(
        animation_name=animation_name,
        frame_size=(10, 10)
    )


def create_custom_sprite_mock(
    animation_name: str,
    frame_size: tuple,
    pixel_color: tuple = (255, 0, 0)
) -> Mock:
    """Create a custom sprite mock with specified parameters."""
    return MockFactory.create_animated_sprite_mock(
        animation_name=animation_name,
        frame_size=frame_size,
        pixel_color=pixel_color
    )


# Template-related mock functions
def create_template_path_mock(template_name: str = "test_template") -> Mock:
    """Create a mock Path object for template testing."""
    mock_path = Mock()
    mock_path.name = template_name
    mock_path.__truediv__ = Mock(return_value=mock_path)
    mock_path.iterdir = Mock()
    mock_path.open = Mock()

    # Create a custom class that properly handles string conversion
    class MockPath:
        def __init__(self, name):
            self.name = name
            self._template_name = name

        def __truediv__(self, other):
            return self

        def iterdir(self):
            return []

        def open(self, *args, **kwargs):
            return Mock()

        def __str__(self):
            return f"/mock/path/{self._template_name}"

        def __repr__(self):
            return f"MockPath('{self._template_name}')"

    return MockPath(template_name)


def create_template_repo_file_mock(repo_url: str = None) -> Mock:  # noqa: RUF013
    """Create a mock .repo file for template testing."""
    mock_file = Mock()
    mock_file.__enter__ = Mock(return_value=mock_file)
    mock_file.__exit__ = Mock(return_value=None)
    if repo_url:
        mock_file.readline.return_value = repo_url
    else:
        mock_file.readline.side_effect = FileNotFoundError()
    return mock_file


def create_template_directory_mock(template_names: list = None) -> Mock:  # noqa: RUF013
    """Create a mock template directory with specified templates."""
    if template_names is None:
        template_names = ["template1", "template2"]

    mock_items = []
    for name in template_names:
        mock_item = Mock()
        mock_item.name = name
        mock_items.append(mock_item)

    mock_path = Mock()
    mock_path.iterdir.return_value = mock_items
    return mock_path
