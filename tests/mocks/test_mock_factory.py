"""Centralized mock factory for test objects.

This module provides reusable mock factories for creating consistent test objects
across all test files, reducing code duplication and ensuring proper mock configuration.
"""

from typing import ClassVar, NamedTuple
from unittest.mock import Mock, patch

import pygame

from glitchygames.events import unhandled_event
from glitchygames.sprites import AnimatedSprite

# Constants for magic values
MIN_ARGS_FOR_DIMENSIONS = 2
DEFAULT_SIZE = 32
MIN_ARGS_FOR_FGCOLOR = 2


class MockSpriteConfig(NamedTuple):
    """Configuration for creating an animated sprite mock."""

    animation_name: str = 'idle'
    frame_size: tuple = (8, 8)
    pixel_color: tuple = (255, 0, 0)
    current_frame: int = 0
    is_playing: bool = False
    is_looping: bool = True


DEFAULT_MOCK_SPRITE_CONFIG = MockSpriteConfig()


class MockSurface(pygame.Surface):
    """Wrapper around pygame.Surface that provides mockable convert methods."""

    def __init__(self, *args, **kwargs):
        """Initialize MockSurface with pygame compatibility."""
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((800, 600))

        # Validate dimensions to prevent invalid surface creation
        if args:
            # Handle both pygame.Surface((width, height)) and pygame.Surface(width, height)
            min_args_for_tuple = 1
            min_args_for_separate = 2
            default_surface_size = 32
            if (
                len(args) >= min_args_for_tuple
                and isinstance(args[0], tuple)
                and len(args[0]) >= min_args_for_separate
            ):
                # Tuple form: pygame.Surface((width, height))
                width, height = args[0]
                # Allow 0x0 surfaces for testing empty surface scenarios
                if isinstance(width, int) and isinstance(height, int) and (width < 0 or height < 0):
                    args = ((default_surface_size, default_surface_size), *args[1:])
            elif len(args) >= min_args_for_separate:
                # Separate args form: pygame.Surface(width, height)
                width, height = args[0], args[1]
                # Allow 0x0 surfaces for testing empty surface scenarios
                if isinstance(width, int) and isinstance(height, int) and (width < 0 or height < 0):
                    args = (default_surface_size, default_surface_size, *args[2:])

        # Initialize the parent pygame.Surface
        super().__init__(*args, **kwargs)  # type: ignore[no-matching-overload]
        self._surface = self  # For compatibility with existing code
        self._mock_path = '/mock/surface/path.png'  # Default mock path for PathLike protocol

    def convert(self, *args, **kwargs):
        """Mock convert method that returns self.

        Returns:
            object: The result.

        """
        return self

    def convert_alpha(self, *args, **kwargs):
        """Mock convert_alpha method that returns self.

        Returns:
            object: The result.

        """
        return self

    def blit(self, source, dest, area=None, special_flags=0):  # type: ignore[invalid-method-override]
        """Delegate blit to the parent surface.

        Returns:
            object: The result.

        """
        # Handle MockSurface sources by extracting their real surface
        if hasattr(source, '_surface'):
            source = source._surface

        # If source is still a mock, create a real surface for it
        if (
            hasattr(source, '_spec_class')
            or str(type(source)).find('Mock') != -1
            or str(type(source)).find('MockSurface') != -1
        ):
            # Create a real pygame surface for the mock by calling the real constructor
            real_source = pygame.surface.Surface((32, 32))
            real_source.fill((255, 255, 255))  # White background
            source = real_source

        # Handle mock destination (position)
        if hasattr(dest, '_spec_class') or str(type(dest)).find('Mock') != -1:
            dest = (0, 0)

        return super().blit(source, dest, area, special_flags)

    def fill(self, color, rect=None, special_flags=0):
        """Delegate fill to the parent surface.

        Returns:
            object: The result.

        """
        return super().fill(color, rect, special_flags)

    def copy(self):
        """Return a copy of this surface.

        Returns:
            MockSurface: A new MockSurface with the same pixel data.

        """
        new_surface = MockSurface(self.get_size(), flags=self.get_flags())
        new_surface.blit(self, (0, 0))
        return new_surface

    def __copy__(self):
        """Support copy.copy() by delegating to copy().

        Returns:
            MockSurface: A shallow copy.

        """
        return self.copy()

    def __deepcopy__(self, memo):
        """Support copy.deepcopy() by creating a new MockSurface with copied pixel data.

        Returns:
            MockSurface: A deep copy.

        """
        new_surface = MockSurface(self.get_size(), flags=self.get_flags())
        new_surface.blit(self, (0, 0))
        memo[id(self)] = new_surface
        return new_surface

    def set_at(self, pos, color):
        """Set pixel color at position.

        Returns:
            object: The result.

        """
        return super().set_at(pos, color)

    def get_at(self, pos):
        """Get pixel color at position.

        Returns:
            object: The at.

        """
        # Get the color from the parent surface and ensure it's a pygame.Color object
        color = super().get_at(pos)
        # If it's a tuple, convert it to pygame.Color
        if isinstance(color, tuple):
            return pygame.Color(*color)
        return color

    def get_pixel_data(self):
        """Get pixel data for this surface.

        Returns:
            object: The pixel data.

        """
        width, height = self.get_size()
        # Return different pixel data based on the surface content
        # This simulates different frame content
        return [(255, 0, 0)] * (width * height)  # Red pixels for testing

    def get_rect(self, **kwargs):
        """Get rect for this surface.

        Returns:
            object: The rect.

        """
        return super().get_rect(**kwargs)

    def __fspath__(self):
        """Implement PathLike protocol for MockSurface.

        Returns:
            object: The result.

        """
        return self._mock_path


class MockFactory:  # noqa: PLR0904
    """Factory class for creating properly configured mock objects."""

    # Cache for expensive mock objects to improve test performance
    _cached_sprites: ClassVar[dict] = {}
    _cached_scenes: ClassVar[dict] = {}
    _cached_frames: ClassVar[dict] = {}

    @staticmethod
    def _copy_mock_sprite(original_sprite: Mock) -> Mock:
        """Create a copy of a mock sprite to avoid test interference.

        Returns:
            Mock: The result.

        """
        # Create a new Mock instead of deep copying to avoid infinite recursion
        new_sprite = Mock(spec=type(original_sprite))

        # Copy essential attributes manually to avoid circular references
        for attr_name in [
            '_animations',
            'current_animation',
            'current_frame',
            'is_playing',
            '_is_looping',
        ]:
            if hasattr(original_sprite, attr_name):
                setattr(new_sprite, attr_name, getattr(original_sprite, attr_name))

        # Copy methods
        for attr_name in dir(original_sprite):
            if not attr_name.startswith('_') and callable(getattr(original_sprite, attr_name)):
                setattr(new_sprite, attr_name, getattr(original_sprite, attr_name))

        return new_sprite

    @staticmethod
    def _clear_cache():
        """Clear all cached mock objects for test isolation."""
        MockFactory._cached_sprites.clear()
        MockFactory._cached_scenes.clear()
        MockFactory._cached_frames.clear()

    @staticmethod
    def _create_mock_frame(frame_index: int, frame_size: tuple, pixel_color: tuple) -> Mock:
        """Create a single mock frame for animation testing.

        Args:
            frame_index: Index of the frame in the animation sequence
            frame_size: Size of the frame as (width, height)
            pixel_color: Base RGB color tuple for pixels

        Returns:
            Configured mock frame with image, rect, pixels, and get_pixel_data

        """
        mock_frame = Mock()
        mock_frame.get_size.return_value = frame_size
        mock_frame.get_width.return_value = frame_size[0]
        mock_frame.get_height.return_value = frame_size[1]

        # Create different pixel colors for each frame to simulate animation
        frame_color = (
            (pixel_color[0] + frame_index * 20) % 256,
            (pixel_color[1] + frame_index * 30) % 256,
            (pixel_color[2] + frame_index * 40) % 256,
        )
        pixel_count = frame_size[0] * frame_size[1]
        mock_frame.get_pixel_data.return_value = [frame_color] * pixel_count

        # Create frame image - use real pygame Surface when pygame is initialized
        # so that film strip rendering (pygame.transform.scale, etc.) works
        if pygame.get_init():
            real_surface = pygame.Surface(frame_size, pygame.SRCALPHA)
            real_surface.fill(frame_color[:3])
            mock_frame.image = real_surface
        else:
            mock_frame_image = Mock()
            mock_frame_image.get_width.return_value = frame_size[0]
            mock_frame_image.get_height.return_value = frame_size[1]
            mock_frame_image.get_size.return_value = frame_size
            mock_frame.image = mock_frame_image

        # Add frame_index for sequence testing
        mock_frame.frame_index = frame_index

        # Add varied duration for timing testing (simulate different frame speeds)
        # Frame 0: 0.3s (fast), Frame 1: 0.7s (normal), Frame 2: 1.0s (slow), etc.
        mock_frame.duration = 0.3 + (frame_index * 0.2)  # 0.3, 0.5, 0.7, 0.9, 1.1

        return mock_frame

    @staticmethod
    def _configure_sprite_basic_playback(mock_sprite: Mock) -> None:
        """Configure basic playback controls on a sprite mock.

        Sets up play, pause, stop, and set_animation closures.

        Args:
            mock_sprite: The mock sprite to configure

        """

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

    @staticmethod
    def _configure_sprite_frame_access(
        mock_sprite: Mock,
        frame_size: tuple,
        pixel_color: tuple,
        pixel_count: int,
    ) -> None:
        """Configure frame access and pixel data methods on a sprite mock.

        Sets up set_frame, get_pixel_data, and get_frame_pixel_data closures
        using a shared frame-lookup helper.

        Args:
            mock_sprite: The mock sprite to configure
            frame_size: Size of frames as (width, height)
            pixel_color: Default RGB color tuple for pixels
            pixel_count: Total number of pixels per frame

        """

        def _get_animation_frames(animation_name=None, frame_idx=None):
            """Get frames for an animation, optionally at a specific index."""
            anim = animation_name or mock_sprite.current_animation
            if anim in mock_sprite._animations:
                frames = mock_sprite._animations[anim]
                if frame_idx is not None and frame_idx < len(frames):
                    return frames[frame_idx]
                return frames
            return None

        def mock_set_frame(frame_idx):
            mock_sprite.current_frame = frame_idx
            # Update the sprite's image and rect to match the current frame
            current_frame = _get_animation_frames(frame_idx=frame_idx)
            if current_frame is not None:
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
            frame = _get_animation_frames(frame_idx=mock_sprite.current_frame)
            if frame is not None:
                return frame.get_pixel_data()
            return [pixel_color] * pixel_count

        mock_sprite.get_pixel_data = mock_get_pixel_data

        # Also add a method to get pixel data for a specific frame
        def mock_get_frame_pixel_data(frame_idx):
            frame = _get_animation_frames(frame_idx=frame_idx)
            if frame is not None:
                return frame.get_pixel_data()
            return [pixel_color] * pixel_count

        mock_sprite.get_frame_pixel_data = mock_get_frame_pixel_data

    @staticmethod
    def _configure_sprite_playback_methods(
        mock_sprite: Mock,
        frame_size: tuple,
        pixel_color: tuple,
        pixel_count: int,
    ) -> None:
        """Configure playback and pixel data methods on a sprite mock.

        Sets up play, pause, stop, set_animation, set_frame, get_pixel_data,
        and get_frame_pixel_data closures.

        Args:
            mock_sprite: The mock sprite to configure
            frame_size: Size of frames as (width, height)
            pixel_color: Default RGB color tuple for pixels
            pixel_count: Total number of pixels per frame

        """
        MockFactory._configure_sprite_basic_playback(mock_sprite)
        MockFactory._configure_sprite_frame_access(
            mock_sprite,
            frame_size,
            pixel_color,
            pixel_count,
        )

    @staticmethod
    def _configure_sprite_animation_crud(mock_sprite: Mock) -> None:
        """Configure animation add/remove, looping, and cache methods on a sprite mock.

        Args:
            mock_sprite: The mock sprite to configure

        """

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

    @staticmethod
    def _configure_sprite_observer_and_metadata(mock_sprite: Mock) -> None:
        """Configure observer, get_frame, metadata, and simple mock methods on a sprite mock.

        Args:
            mock_sprite: The mock sprite to configure

        """

        def _validate_animation_exists(animation_name):
            """Validate that an animation exists and return its frames.

            Raises:
                ValueError: If the animation does not exist.

            """
            if animation_name not in mock_sprite._animations:
                msg = f"Animation '{animation_name}' not found"
                raise ValueError(msg)
            return mock_sprite._animations[animation_name]

        def mock_add_frame_observer(observer):
            mock_sprite._frame_manager._observers.append(observer)

        mock_sprite.add_frame_observer = mock_add_frame_observer

        def mock_remove_frame_observer(observer):
            if observer in mock_sprite._frame_manager._observers:
                mock_sprite._frame_manager._observers.remove(observer)

        mock_sprite.remove_frame_observer = mock_remove_frame_observer

        # Add get_frame method with error handling
        def mock_get_frame(animation_name, frame_idx):
            frames = _validate_animation_exists(animation_name)
            if frame_idx < 0 or frame_idx >= len(frames):
                msg = f"Frame index {frame_idx} out of range for animation '{animation_name}'"
                raise IndexError(msg)
            return frames[frame_idx]

        mock_sprite.get_frame = mock_get_frame

        # Add get_animation_metadata method
        def mock_get_animation_metadata(animation_name):
            frames = _validate_animation_exists(animation_name)
            return {
                'name': animation_name,
                'frame_count': len(frames),
                'total_duration': sum(frame.duration for frame in frames),
                'is_looping': mock_sprite._is_looping,
            }

        mock_sprite.get_animation_metadata = mock_get_animation_metadata

        mock_sprite.get_current_surface = Mock(return_value=Mock())
        mock_sprite.save = Mock()
        mock_sprite.load = Mock()

    @staticmethod
    def _configure_sprite_animation_management(mock_sprite: Mock) -> None:
        """Configure animation management, observer, and metadata methods on a sprite mock.

        Sets up add/remove animation, looping, cache, observer, get_frame,
        get_animation_metadata, and simple mock methods.

        Args:
            mock_sprite: The mock sprite to configure

        """
        MockFactory._configure_sprite_animation_crud(mock_sprite)
        MockFactory._configure_sprite_observer_and_metadata(mock_sprite)

    @staticmethod
    def _configure_sprite_methods(
        mock_sprite: Mock,
        frame_size: tuple,
        pixel_color: tuple,
        pixel_count: int,
    ) -> None:
        """Configure all methods on a sprite mock.

        Delegates to _configure_sprite_playback_methods and
        _configure_sprite_animation_management.

        Args:
            mock_sprite: The mock sprite to configure
            frame_size: Size of frames as (width, height)
            pixel_color: Default RGB color tuple for pixels
            pixel_count: Total number of pixels per frame

        """
        MockFactory._configure_sprite_playback_methods(
            mock_sprite,
            frame_size,
            pixel_color,
            pixel_count,
        )
        MockFactory._configure_sprite_animation_management(mock_sprite)

    @staticmethod
    def _setup_default_event_handler(
        scene_mock: Mock,
        handler_name: str,
        event_list: list,
        tag: str | None = None,
    ) -> None:
        """Create and attach a default event handler to a scene mock.

        Args:
            scene_mock: The scene mock to attach the handler to
            handler_name: The name of the handler method (e.g., 'on_audio_device_added_event')
            event_list: The list to append events to
            tag: Optional tag to prepend as a tuple (tag, event) instead of just event

        """
        if tag is not None:

            def tagged_handler(event, _tag=tag, _event_list=event_list):
                _event_list.append((_tag, event))

            handler = tagged_handler
        else:

            def untagged_handler(event, _event_list=event_list):
                _event_list.append(event)
                return True

            handler = untagged_handler

        setattr(scene_mock, handler_name, handler)

    @staticmethod
    def _setup_mock_rect(x: int, y: int, width: int, height: int) -> Mock:
        """Create a mock rect with all standard pygame.Rect position properties.

        Args:
            x: X coordinate
            y: Y coordinate
            width: Width of the rect
            height: Height of the rect

        Returns:
            Mock rect with all position properties configured

        """
        mock_rect = Mock()
        mock_rect.x = x
        mock_rect.y = y
        mock_rect.width = width
        mock_rect.height = height
        mock_rect.midleft = (x, y + height // 2)
        mock_rect.midright = (x + width, y + height // 2)
        mock_rect.midtop = (x + width // 2, y)
        mock_rect.midbottom = (x + width // 2, y + height)
        mock_rect.center = (x + width // 2, y + height // 2)
        mock_rect.topleft = (x, y)
        mock_rect.topright = (x + width, y)
        mock_rect.bottomleft = (x, y + height)
        mock_rect.bottomright = (x + width, y + height)
        mock_rect.centerx = x + width // 2
        mock_rect.centery = y + height // 2
        mock_rect.left = x
        mock_rect.right = x + width
        mock_rect.top = y
        mock_rect.bottom = y + height
        return mock_rect

    @staticmethod
    def create_animated_sprite_mock(config: MockSpriteConfig = DEFAULT_MOCK_SPRITE_CONFIG) -> Mock:
        """Create a properly configured AnimatedSprite mock.

        Args:
            config: Configuration for the sprite mock including animation name,
                frame size, pixel color, current frame, and playback state.

        Returns:
            Properly configured AnimatedSprite mock

        """
        animation_name = config.animation_name
        frame_size = config.frame_size
        pixel_color = config.pixel_color
        current_frame = config.current_frame
        is_playing = config.is_playing
        is_looping = config.is_looping

        # Create the mock sprite
        mock_sprite = Mock(spec=AnimatedSprite)

        # Create multiple frames for animation simulation
        num_frames = 5  # Simulate 5 different frames
        mock_frames = [
            MockFactory._create_mock_frame(frame_idx, frame_size, pixel_color)
            for frame_idx in range(num_frames)
        ]

        pixel_count = frame_size[0] * frame_size[1]

        # Add pixels attribute to the first frame for surface creation
        mock_frames[0].pixels = [pixel_color] * pixel_count

        # Create animations for testing
        mock_sprite._animations = {
            animation_name: mock_frames,
            'timing_demo': mock_frames,  # Add timing_demo animation for tests
        }
        # Expose animation_data as public alias (mirrors AnimatedSprite.animation_data property)
        mock_sprite.animation_data = mock_sprite._animations

        # Only add "idle" if it's specifically requested
        if animation_name == 'idle':
            mock_sprite._animations['idle'] = mock_frames
        mock_sprite.current_animation = animation_name  # Set to the provided animation name
        mock_sprite.current_frame = current_frame  # Start with specified frame
        mock_sprite.is_playing = is_playing
        mock_sprite._is_looping = is_looping
        mock_sprite.name = 'Tiley McTile Face'  # Default name for tests

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

        # Add animation_order attribute that canvas_interfaces.py expects
        mock_sprite.animation_order = list(mock_sprite._animations.keys())

        # Add clear_surface_cache method that canvas_interfaces.py expects
        mock_sprite.clear_surface_cache = Mock()

        # Add missing attributes (must be set before _configure_sprite_methods)
        mock_sprite._surface_cache = {}
        mock_sprite._frame_manager = Mock()
        mock_sprite._frame_manager._observers = []
        mock_sprite._frame_manager.animated_sprite = mock_sprite

        # Configure all methods (play, pause, stop, set_animation, set_frame, etc.)
        MockFactory._configure_sprite_methods(mock_sprite, frame_size, pixel_color, pixel_count)

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

        return mock_sprite

    @staticmethod
    def create_optimized_scene_mock(
        pixels_across: int = 32,
        pixels_tall: int = 32,
        pixel_size: int = 16,
        *,
        use_cache: bool = True,  # noqa: ARG004
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

        return scene_mock

    @staticmethod
    def create_event_test_scene_mock(
        options: dict | None = None,
        event_handlers: dict | None = None,
        *,
        use_cache: bool = True,  # noqa: ARG004
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
                'debug_events': False,
                'no_unhandled_events': True,  # Enable globally to catch unhandled events as bugs
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

            unhandled_fallback_handler_names = [
                'on_controller_axis_motion_event',
                'on_audio_device_added_event',
                'on_font_changed_event',
                'on_quit_event',
                'on_active_event',
                'on_user_event',
                'on_video_resize_event',
                'on_game_event',
                'on_menu_item_event',
                'on_joy_axis_motion_event',
                'on_joy_button_down_event',
                'on_joy_button_up_event',
                'on_joy_device_added_event',
                'on_joy_device_removed_event',
                'on_joy_hat_motion_event',
                'on_joy_ball_motion_event',
                'on_midi_in_event',
                'on_midi_out_event',
                'on_text_input_event',
                'on_text_editing_event',
                'on_render_device_reset_event',
                'on_render_targets_reset_event',
                'on_clipboard_update_event',
                'on_locale_changed_event',
                'on_app_did_enter_background_event',
                'on_app_did_enter_foreground_event',
                'on_app_will_enter_background_event',
                'on_app_will_enter_foreground_event',
                'on_app_low_memory_event',
                'on_app_terminating_event',
            ]
            for handler_name in unhandled_fallback_handler_names:
                setattr(scene_mock, handler_name, unhandled_event_fallback)
        else:
            # Add default event handlers if not provided.
            # Each entry: (handler_name, event_list_attr, tag_or_none)
            # tag=None means append event directly and return True;
            # tag=string means append (tag, event) tuple with no return value.
            default_handler_definitions = [
                ('on_audio_device_added_event', 'audio_events_received', None),
                ('on_controller_axis_motion_event', 'controller_events_received', None),
                ('on_text_input_event', 'text_events_received', None),
                ('on_text_editing_event', 'text_events_received', None),
                ('on_render_device_reset_event', 'game_events_received', 'render_device_reset'),
                ('on_render_targets_reset_event', 'game_events_received', 'render_targets_reset'),
                (
                    'on_app_did_enter_background_event',
                    'game_events_received',
                    'app_did_enter_background',
                ),
                (
                    'on_app_did_enter_foreground_event',
                    'game_events_received',
                    'app_did_enter_foreground',
                ),
                (
                    'on_app_will_enter_background_event',
                    'game_events_received',
                    'app_will_enter_background',
                ),
                (
                    'on_app_will_enter_foreground_event',
                    'game_events_received',
                    'app_will_enter_foreground',
                ),
                ('on_app_low_memory_event', 'game_events_received', 'app_low_memory'),
                ('on_app_terminating_event', 'game_events_received', 'app_terminating'),
                ('on_clipboard_update_event', 'game_events_received', 'clipboard_update'),
                ('on_locale_changed_event', 'game_events_received', 'locale_changed'),
            ]

            for handler_name, event_list_attr, tag in default_handler_definitions:
                if event_handlers is None or handler_name not in event_handlers:
                    event_list = getattr(scene_mock, event_list_attr)
                    MockFactory._setup_default_event_handler(
                        scene_mock,
                        handler_name,
                        event_list,
                        tag,
                    )

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
        mock_canvas.current_animation = ''
        mock_canvas.current_frame = 0
        mock_canvas.animated_sprite = None

        # Set up rect with real values
        mock_canvas.rect = Mock()
        mock_canvas.rect.x = 0
        mock_canvas.rect.y = 0
        mock_canvas.rect.width = pixels_across * 16  # pixel_size * pixels_across
        mock_canvas.rect.height = pixels_tall * 16  # pixel_size * pixels_tall
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
    def create_sprite_frame_mock(size: tuple = (8, 8), pixel_color: tuple = (255, 0, 0)) -> Mock:
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

        # Create frame image - use real pygame Surface when pygame is initialized
        # so that film strip rendering (pygame.transform.scale, etc.) works
        if pygame.get_init():
            real_surface = pygame.Surface(size, pygame.SRCALPHA)
            real_surface.fill(pixel_color[:3])
            mock_frame.image = real_surface
        else:
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
        """Create a pygame.Surface-like mock suitable for Sprite tests.

        Returns:
            object: The newly created pygame surface mock.

        """
        # Use the MockSurface class that inherits from pygame.Surface
        # This ensures it's recognized as a pygame.Surface instance
        return MockSurface((width, height))

    @staticmethod
    def create_pygame_surface_mock_object(width: int = 8, height: int = 8):
        """Create a Mock object that can have its methods mocked.

        For tests that need to set return_value.

        Returns:
            object: The newly created pygame surface mock object.

        """
        mock_surface = Mock()
        mock_surface.get_width.return_value = width
        mock_surface.get_height.return_value = height
        mock_surface.get_size.return_value = (width, height)
        mock_surface.get_width.return_value = width
        mock_surface.get_height.return_value = height
        mock_surface.get_size.return_value = (width, height)
        mock_surface.make_surface.return_value = mock_surface
        return mock_surface

    @staticmethod
    def _create_real_pygame_surface(width: int = 8, height: int = 8):
        """Create a real pygame.Surface for tests that need actual pygame functionality.

        Returns:
            object: The newly created real pygame surface.

        """
        import pygame

        # Initialize pygame if not already initialized
        if not pygame.get_init():
            pygame.init()
        return pygame.Surface((width, height))

    @staticmethod
    def create_pygame_font_mock():
        """Create a mock pygame font for testing.

        Returns:
            object: The newly created pygame font mock.

        """
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
        """Create a mock pygame event for testing.

        Returns:
            object: The newly created pygame event mock.

        """
        mock_event = Mock()
        mock_event.type = 0
        mock_event.pos = (0, 0)
        mock_event.button = 1
        mock_event.key = 0
        mock_event.unicode = ''
        mock_event.text = ''
        return mock_event

    @staticmethod
    def create_pygame_key_mock(*, shift_pressed=False):
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
        """Create a mock pygame joystick for testing.

        Returns:
            object: The newly created pygame joystick mock.

        """
        mock_joystick = Mock()
        mock_joystick.get_name.return_value = 'Mock Joystick'
        mock_joystick.get_numaxes.return_value = 2
        mock_joystick.get_numbuttons.return_value = 8
        mock_joystick.get_numhats.return_value = 1
        mock_joystick.get_axis.return_value = 0.0
        mock_joystick.get_button.return_value = False
        mock_joystick.get_hat.return_value = (0, 0)
        return mock_joystick

    @staticmethod
    def create_pygame_sprite_group_mock():
        """Create a mock pygame sprite group for testing.

        Returns:
            object: The newly created pygame sprite group mock.

        """
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
        """Create a mock game for testing.

        Returns:
            object: The newly created game mock.

        """
        mock_game = Mock()
        mock_game.NAME = 'MockGame'
        mock_game.VERSION = '1.0'
        mock_game.args = Mock(return_value=Mock())
        return mock_game

    @staticmethod
    def create_joystick_manager_mock(joystick_count: int = 0) -> Mock:
        """Create a properly configured JoystickEventManager mock.

        Args:
            joystick_count: Number of joysticks to simulate (default: 0)

        Returns:
            Properly configured JoystickEventManager mock

        """
        mock_manager = Mock()
        # Create a dictionary of joystick proxies (empty by default)
        mock_joysticks = {}
        for i in range(joystick_count):
            mock_joystick_proxy = Mock()
            mock_joystick_proxy._id = i
            mock_joystick_proxy.get_name.return_value = f'Mock Joystick {i}'
            mock_joystick_proxy.get_numaxes.return_value = 4
            mock_joystick_proxy.get_numbuttons.return_value = 12
            mock_joystick_proxy.get_numhats.return_value = 1
            mock_joystick_proxy.get_numballs.return_value = 0
            mock_joysticks[i] = mock_joystick_proxy

        mock_manager.joysticks = mock_joysticks
        return mock_manager

    @staticmethod
    def create_pygame_surface_class_mock():
        """Create a pygame.Surface class mock that works with isinstance checks.

        Returns:
            object: The newly created pygame surface class mock.

        """

        # Create a mock class that can be used with isinstance
        class MockSurfaceClass:
            def __init__(self, *args, **kwargs):
                # Extract dimensions from constructor arguments
                if len(args) >= 1:
                    if (
                        isinstance(args[0], (tuple, list))
                        and len(args[0]) >= MIN_ARGS_FOR_DIMENSIONS
                    ):
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
                    if not attr.startswith('_'):
                        setattr(self, attr, getattr(self._mock_surface, attr))

        # Make it look like a proper class
        MockSurfaceClass.__name__ = 'Surface'
        MockSurfaceClass.__module__ = 'pygame'

        # Store the class for isinstance checks
        MockFactory._surface_class = MockSurfaceClass  # type: ignore[unresolved-attribute]

        return MockSurfaceClass

    @staticmethod
    def create_display_mock(width: int = 800, height: int = 600) -> MockSurface:
        """Create a mock for pygame.display.get_surface().

        Returns:
            MockSurface: The newly created display mock.

        """
        # Create a MockSurface that behaves like a pygame.Surface
        screen = MockSurface((width, height))

        # Override methods to return expected values
        screen.get_width = Mock(return_value=width)  # type: ignore[invalid-assignment]
        screen.get_height = Mock(return_value=height)  # type: ignore[invalid-assignment]
        screen.get_size = Mock(return_value=(width, height))  # type: ignore[invalid-assignment]

        # Provide surface methods that Scene class calls
        screen.convert = Mock(return_value=screen)  # type: ignore[invalid-assignment]
        screen.convert_alpha = Mock(return_value=screen)  # type: ignore[invalid-assignment]
        screen.blit = Mock(return_value=None)  # type: ignore[invalid-assignment]
        screen.fill = Mock(return_value=None)  # type: ignore[invalid-assignment]
        screen.copy = Mock(return_value=screen)  # type: ignore[invalid-assignment]
        screen.set_at = Mock(return_value=None)  # type: ignore[invalid-assignment]
        screen.get_at = Mock(return_value=pygame.Color(0, 0, 0, 255))  # type: ignore[invalid-assignment]

        # Provide a minimal screen rect-like attributes used by paddles
        screen.left = 0  # type: ignore[unresolved-attribute]
        screen.right = width  # type: ignore[unresolved-attribute]
        screen.top = 0  # type: ignore[unresolved-attribute]
        screen.bottom = height  # type: ignore[unresolved-attribute]

        # Add get_rect method that returns a mock with center attribute
        rect_mock = Mock()
        rect_mock.center = (width // 2, height // 2)
        screen.get_rect = Mock(return_value=rect_mock)  # type: ignore[invalid-assignment]

        return screen

    @staticmethod
    def _mock_sprite_init(self, *args, **kwargs):  # noqa: PLW0211, ARG004  # pyright: ignore[reportSelfClsParameterName]
        """Mock Sprite.__init__ that handles pygame.display.get_surface() properly."""
        # Avoid referencing self in debug output to prevent __str__ access before attributes are set
        # Extract arguments from kwargs since that's how they're being passed
        x = kwargs.get('x', 0)
        y = kwargs.get('y', 0)
        width = kwargs.get('width', 32)
        height = kwargs.get('height', 32)
        name = kwargs.get('name', '')
        parent = kwargs.get('parent')
        groups = kwargs.get('groups')

        # Set essential identifiers early
        self.name = name
        self.parent = parent

        # BitmappySprite-specific attributes
        self.filename = kwargs.get('filename', '')
        self.focusable = kwargs.get('focusable', False)
        self.is_active = False

        # Initialize pixel data attributes
        self.pixels = []
        self.pixels_across = width
        self.pixels_tall = height

        # Ensure proper inheritance by setting __class__ if needed
        # This helps with isinstance() checks in tests
        if hasattr(self, '__class__'):
            # Make sure the class hierarchy is preserved
            pass

        # Add private _text attribute for TextSprite (must be set early)
        self._text = ''

        # Add background_color attribute for TextSprite
        self.background_color = (0, 0, 0, 0)  # Transparent black by default

        # Add text_color attribute for TextSprite
        self.text_color = (255, 255, 255)  # White text by default

        # CRITICAL: Set up rect FIRST, before any operations that might access it
        self.rect = MockFactory._setup_mock_rect(x, y, width, height)

        # pygame sprites expect groups() to be a method, not a list
        self._groups_list = groups or []

        # For pygame.sprite.Sprite.add() calls, we need groups to be iterable
        # So we set it as a property that returns the list
        self._groups = self._groups_list

        # Create a groups method that returns the list - pygame expects groups() to be callable
        self.groups = lambda: self._groups_list

        # Add common UI component attributes that might be accessed
        # Note: TextSprite manages its own text property, so we don't set self.text here

        # For ButtonSprite, we need to ensure that when TextSprite
        # is created, it has the right attributes.
        # This will be handled by the TextSprite mock constructor

        # Add x and y properties for TextSprite compatibility
        self._x = x
        self._y = y

        # pygame sprites expect __g to be a dict (Sprite.add_internal does self.__g[group] = 0)
        self.__g = {}

        # Establish dirty/visible flags BEFORE property setters use them
        self.dirty = 1
        self.visible = 1
        self._Sprite__dirty = 1
        self._Sprite__visible = 1

        # Add pygame sprite required attributes
        self.blendmode = 0  # pygame.BLEND_NORMAL

        # Now set basic attributes - use private attributes to avoid
        # triggering property setters that might reference attributes
        # not yet initialized (e.g., ButtonSprite.x setter -> self.text)
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
        # pygame.sprite.Sprite.add_internal does self.__g[group] = 0, so __g must be a dict
        self._Sprite__g = {}

    @staticmethod
    def create_pygame_display_mock() -> Mock:
        """Create a comprehensive pygame.display mock with initialization.

        Returns:
            Mock: The newly created pygame display mock.

        """
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
        display_mock.get_caption.return_value = ('Test Game', 'Test Game')

        # Add Info class to display mock
        class MockDisplayInfo:
            def __init__(self):
                self.current_w = 1280
                self.current_h = 720

        display_mock.Info = MockDisplayInfo
        return display_mock

    @staticmethod
    def _setup_minimal_pygame_mocks():
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
        display_patcher = patch('pygame.display', display_mock)
        display_get_surface_patcher = patch(
            'pygame.display.get_surface',
            return_value=display_surface,
        )

        return (display_patcher, display_get_surface_patcher)

    @staticmethod
    def _attach_layered_dirty_draw(mock_group: Mock) -> None:
        """Attach the draw method to a mock layered dirty group.

        Args:
            mock_group: The mock group to attach the draw method to

        """

        def _sprite_has_image_and_rect(sprite):
            """Check if a sprite has both image and rect attributes."""
            return hasattr(sprite, 'image') and hasattr(sprite, 'rect')

        def mock_draw(surface):
            """Mock draw method that handles sprites properly."""
            for sprite in mock_group._spritelist:
                if not _sprite_has_image_and_rect(sprite):
                    continue
                if sprite not in mock_group._old_rect:
                    mock_group._old_rect[sprite] = sprite.rect.copy()
                surface.blit(sprite.image, sprite.rect)

        mock_group.draw = mock_draw

    @staticmethod
    def _attach_layered_dirty_add_remove(mock_group: Mock) -> None:
        """Attach add and remove methods to a mock layered dirty group.

        Args:
            mock_group: The mock group to attach methods to

        """

        def mock_add(*sprites):
            """Mock add method."""
            for sprite in sprites:
                if sprite not in mock_group._spritelist:
                    mock_group._spritelist.append(sprite)
                    if hasattr(sprite, 'rect'):
                        mock_group._old_rect[sprite] = sprite.rect.copy()

        def mock_remove(*sprites):
            """Mock remove method."""
            for sprite in sprites:
                if sprite in mock_group._spritelist:
                    mock_group._spritelist.remove(sprite)
                if sprite in mock_group._old_rect:
                    del mock_group._old_rect[sprite]

        mock_group.add = mock_add
        mock_group.remove = mock_remove

    @staticmethod
    def _create_mock_layered_dirty(*args, **kwargs):  # noqa: ARG004
        """Mock pygame.sprite.LayeredDirty constructor that returns a working mock.

        Returns:
            object: A mock sprite group with draw, add, and remove methods.

        """
        mock_group = Mock()
        mock_group._spritelist = []
        mock_group._old_rect = {}
        mock_group._clip = None

        MockFactory._attach_layered_dirty_draw(mock_group)
        MockFactory._attach_layered_dirty_add_remove(mock_group)

        mock_group.__iter__ = lambda self: iter(mock_group._spritelist)
        mock_group.__len__ = lambda self: len(mock_group._spritelist)
        mock_group.__contains__ = lambda self, sprite: sprite in mock_group._spritelist

        return mock_group

    @staticmethod
    def _mock_sprite_factory_load_sprite(*, filename: str | None = None):  # noqa: ARG004
        """Mock SpriteFactory.load_sprite to return a mocked animated sprite.

        Returns:
            object: A mocked animated sprite.

        """
        return MockFactory.create_animated_sprite_mock(
            config=MockSpriteConfig(
                animation_name='idle',
                frame_size=(8, 8),
                pixel_color=(255, 0, 0),
                current_frame=0,
                is_playing=True,
                is_looping=True,
            ),
        )

    @staticmethod
    def _mock_image_tostring(surface, format_str):
        """Mock pygame.image.tostring that returns mock pixel data.

        Returns:
            object: Mock pixel data bytes.

        """
        # Use format_str to avoid unused argument warning
        _ = format_str
        # Return mock pixel data based on surface size
        if hasattr(surface, 'get_width') and hasattr(surface, 'get_height'):
            width = surface.get_width()
            height = surface.get_height()

            # Check if this is a single-color surface (for legacy sprite tests)
            # If the surface has a single color, return consistent pixel data
            if hasattr(surface, '_test_single_color') and surface._test_single_color:
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
        return b'\x00' * 100  # Default mock data

    @staticmethod
    def _mock_transform_scale(surface, size):
        """Mock pygame.transform.scale that returns a real surface.

        Returns:
            object: A real pygame Surface of the given size.

        """
        import pygame

        # Use surface to avoid unused argument warning
        _ = surface
        return pygame.Surface(size)

    @staticmethod
    def _create_mock_objects():
        """Create all mock objects and side-effect closures for pygame patching.

        Returns:
            dict: A dictionary containing the mock objects and closures needed
                  by _build_core_patch_definitions and _build_event_constant_patches.

        """
        import pygame

        # Create comprehensive mocks
        display_mock = MockFactory.create_pygame_display_mock()
        display_surface = display_mock.get_surface.return_value
        surface_class_mock = MockFactory.create_pygame_surface_class_mock()

        # Draw function mocking - capture original before patching
        original_draw_polygon = pygame.draw.polygon

        def mock_draw_polygon(surface, color, points, width=0):
            """Mock pygame.draw.polygon that handles MockSurface objects.

            Returns:
                object: The result.

            """
            if hasattr(surface, '_surface'):
                # Use the original pygame.draw.polygon directly to avoid recursion
                return original_draw_polygon(surface._surface, color, points, width)
            # For mock surfaces, just return without doing anything
            return None

        # Sound/mixer mocking
        mixer_mock = Mock()
        mixer_mock.Sound.return_value = Mock()
        mixer_mock.get_init.return_value = (22050, -16, 2)  # frequency, format, channels

        # Keyboard mocking
        key_mock = Mock()
        key_mock.set_repeat.return_value = None
        key_mock.get_mods.return_value = 0  # No modifier keys pressed by default
        key_mock.get_pressed.return_value = [False] * 512  # All keys not pressed by default

        # FontManager mock - create a mock font that returns a proper surface
        mock_font = MockFactory._create_mock_font()
        # Override font size for freetype fonts
        mock_font.size = 24  # For freetype fonts

        # Clock mocking
        clock_mock = Mock()
        clock_mock.tick.return_value = 16.67  # ~60 FPS
        clock_mock.get_fps.return_value = 60.0

        return {
            'display_mock': display_mock,
            'display_surface': display_surface,
            'surface_class_mock': surface_class_mock,
            'mock_layered_dirty_constructor': MockFactory._create_mock_layered_dirty,
            'mock_sprite_factory_load_sprite': MockFactory._mock_sprite_factory_load_sprite,
            'mock_draw_polygon': mock_draw_polygon,
            'mixer_mock': mixer_mock,
            'key_mock': key_mock,
            'mock_transform_scale': MockFactory._mock_transform_scale,
            'mock_font': mock_font,
            'mock_image_tostring': MockFactory._mock_image_tostring,
            'clock_mock': clock_mock,
        }

    @staticmethod
    def _create_mock_font():
        """Create a mock font object with render and render_to methods.

        Returns:
            Mock: A configured mock font object.

        """
        mock_font = Mock()

        # Create a mock surface for text rendering that handles all render signatures
        def mock_render(*args, **kwargs):
            """Mock font render that creates real surfaces.

            Returns:
                object: The result.

            """
            # Handle different render method signatures
            text = str(args[0]) if len(args) >= 1 else 'Mock'

            # Create a real surface for text rendering
            import pygame

            if not pygame.get_init():
                pygame.init()

            # Create a real surface with approximate text dimensions
            width = len(text) * 8  # Approximate text width
            height = 16  # Default height
            surface = pygame.Surface((width, height), pygame.SRCALPHA)
            surface.fill((0, 0, 0, 0))  # Transparent background

            # Create a real rect for the text
            text_rect = pygame.Rect(0, 0, width, height)
            surface.get_rect = Mock(return_value=text_rect)  # type: ignore[invalid-assignment]

            # Handle different return types (surface vs (surface, rect))
            if 'fgcolor' in kwargs or len(args) >= MIN_ARGS_FOR_FGCOLOR:
                # pygame.freetype style - return (surface, rect)
                return surface, text_rect
            # pygame.font style - return surface
            return surface

        # Handle both render and render_to methods
        mock_font.render = mock_render
        mock_font.render_to = Mock(return_value=Mock())
        mock_font.get_linesize.return_value = 24  # Default line height
        mock_font.size = Mock(return_value=(100, 16))  # (width, height)

        return mock_font

    @staticmethod
    def _build_core_patch_definitions(mock_objects):
        """Build patch definitions for core pygame subsystems.

        Args:
            mock_objects: Dict of mock objects from _create_mock_objects().

        Returns:
            dict: Mapping of patch name to (target_string, kwargs_dict).

        """
        return {
            # Display mocks
            'display': ('pygame.display', {'new': mock_objects['display_mock']}),
            'display_get_surface': (
                'pygame.display.get_surface',
                {'return_value': mock_objects['display_surface']},
            ),
            # Surface mocking
            'surface': ('pygame.Surface', {'new': mock_objects['surface_class_mock']}),
            # Event mocking
            'event_get': ('pygame.event.get', {'return_value': []}),
            'event_get_blocked': ('pygame.event.get_blocked', {'return_value': False}),
            'event_post': ('pygame.event.post', {}),
            'event_event': ('pygame.event.Event', {}),
            # Drawing mocks for Film Strip and other modules
            'draw_circle': ('pygame.draw.circle', {}),
            'draw_line': ('pygame.draw.line', {}),
            'draw_rect': ('pygame.draw.rect', {}),
            'draw_polygon': (
                'pygame.draw.polygon',
                {'side_effect': mock_objects['mock_draw_polygon']},
            ),
            # Sprite group mocking
            'layered_dirty': (
                'pygame.sprite.LayeredDirty',
                {'side_effect': mock_objects['mock_layered_dirty_constructor']},
            ),
            'sprite_group': (
                'pygame.sprite.Group',
                {'side_effect': mock_objects['mock_layered_dirty_constructor']},
            ),
            # SpriteFactory mocking
            'sprite_factory': (
                'glitchygames.sprites.SpriteFactory.load_sprite',
                {'side_effect': mock_objects['mock_sprite_factory_load_sprite']},
            ),
            # Sound/mixer mocking
            'mixer': ('pygame.mixer', {'new': mock_objects['mixer_mock']}),
            'mixer_sound': ('pygame.mixer.Sound', {'return_value': Mock()}),
            # Keyboard mocking
            'key': ('pygame.key', {'new': mock_objects['key_mock']}),
            # Transform mocking
            'transform_scale': (
                'pygame.transform.scale',
                {'side_effect': mock_objects['mock_transform_scale']},
            ),
            # Image module mock (tostring is deprecated, tobytes is the replacement)
            'image_tostring': (
                'pygame.image.tostring',
                {'side_effect': mock_objects['mock_image_tostring']},
            ),
            'image_tobytes': (
                'pygame.image.tobytes',
                {'side_effect': mock_objects['mock_image_tostring']},
            ),
            # FontManager mock
            'font_manager': (
                'glitchygames.fonts.FontManager.get_font',
                {'return_value': mock_objects['mock_font']},
            ),
            # Clock mocking
            'clock': ('pygame.time.Clock', {'return_value': mock_objects['clock_mock']}),
            # Sprite class mocking - patch the BitmappySprite constructor
            # to handle pygame.display.get_surface()
            'sprite_init': (
                'glitchygames.sprites.BitmappySprite.__init__',
                {'new': MockFactory._mock_sprite_init},
            ),
            # Key constants mocking
            'K_q': ('pygame.K_q', {'new': 113}),
            'K_ESCAPE': ('pygame.K_ESCAPE', {'new': 27}),
            'K_LSHIFT': ('pygame.K_LSHIFT', {'new': 304}),
            'K_RSHIFT': ('pygame.K_RSHIFT', {'new': 303}),
        }

    @staticmethod
    def _build_event_constant_patches():
        """Build patch definitions for pygame event type constants.

        Returns:
            dict: Mapping of patch name to (target_string, kwargs_dict).

        """
        import pygame

        return {
            # Keyboard events
            'KEYDOWN': ('pygame.KEYDOWN', {'new': pygame.KEYDOWN}),
            'KEYUP': ('pygame.KEYUP', {'new': pygame.KEYUP}),
            # Mouse events
            'MOUSEBUTTONDOWN': ('pygame.MOUSEBUTTONDOWN', {'new': pygame.MOUSEBUTTONDOWN}),
            'MOUSEBUTTONUP': ('pygame.MOUSEBUTTONUP', {'new': pygame.MOUSEBUTTONUP}),
            'MOUSEMOTION': ('pygame.MOUSEMOTION', {'new': pygame.MOUSEMOTION}),
            'MOUSEWHEEL': ('pygame.MOUSEWHEEL', {'new': pygame.MOUSEWHEEL}),
            # Window/system events
            'QUIT': ('pygame.QUIT', {'new': pygame.QUIT}),
            'TEXTINPUT': ('pygame.TEXTINPUT', {'new': pygame.TEXTINPUT}),
            # Touch events
            'FINGERDOWN': ('pygame.FINGERDOWN', {'new': pygame.FINGERDOWN}),
            'FINGERUP': ('pygame.FINGERUP', {'new': pygame.FINGERUP}),
            'FINGERMOTION': ('pygame.FINGERMOTION', {'new': pygame.FINGERMOTION}),
            # Window events
            'WINDOWRESIZED': ('pygame.WINDOWRESIZED', {'new': pygame.WINDOWRESIZED}),
            'WINDOWRESTORED': ('pygame.WINDOWRESTORED', {'new': pygame.WINDOWRESTORED}),
            'WINDOWFOCUSGAINED': (
                'pygame.WINDOWFOCUSGAINED',
                {'new': pygame.WINDOWFOCUSGAINED},
            ),
            'WINDOWFOCUSLOST': ('pygame.WINDOWFOCUSLOST', {'new': pygame.WINDOWFOCUSLOST}),
            # Audio events - use real pygame constants
            'AUDIODEVICEADDED': (
                'pygame.AUDIODEVICEADDED',
                {'new': pygame.AUDIODEVICEADDED},
            ),
            'AUDIODEVICEREMOVED': (
                'pygame.AUDIODEVICEREMOVED',
                {'new': pygame.AUDIODEVICEREMOVED},
            ),
            # Joystick/Controller events
            'JOYAXISMOTION': ('pygame.JOYAXISMOTION', {'new': pygame.JOYAXISMOTION}),
            'JOYBALLMOTION': ('pygame.JOYBALLMOTION', {'new': pygame.JOYBALLMOTION}),
            'JOYBUTTONDOWN': ('pygame.JOYBUTTONDOWN', {'new': pygame.JOYBUTTONDOWN}),
            'JOYBUTTONUP': ('pygame.JOYBUTTONUP', {'new': pygame.JOYBUTTONUP}),
            'JOYHATMOTION': ('pygame.JOYHATMOTION', {'new': pygame.JOYHATMOTION}),
            'JOYDEVICEADDED': ('pygame.JOYDEVICEADDED', {'new': pygame.JOYDEVICEADDED}),
            'JOYDEVICEREMOVED': ('pygame.JOYDEVICEREMOVED', {'new': pygame.JOYDEVICEREMOVED}),
            # Controller events
            'CONTROLLERAXISMOTION': (
                'pygame.CONTROLLERAXISMOTION',
                {'new': pygame.CONTROLLERAXISMOTION},
            ),
            'CONTROLLERBUTTONDOWN': (
                'pygame.CONTROLLERBUTTONDOWN',
                {'new': pygame.CONTROLLERBUTTONDOWN},
            ),
            'CONTROLLERBUTTONUP': (
                'pygame.CONTROLLERBUTTONUP',
                {'new': pygame.CONTROLLERBUTTONUP},
            ),
            'CONTROLLERDEVICEADDED': (
                'pygame.CONTROLLERDEVICEADDED',
                {'new': pygame.CONTROLLERDEVICEADDED},
            ),
            'CONTROLLERDEVICEREMOVED': (
                'pygame.CONTROLLERDEVICEREMOVED',
                {'new': pygame.CONTROLLERDEVICEREMOVED},
            ),
            'CONTROLLERDEVICEREMAPPED': (
                'pygame.CONTROLLERDEVICEREMAPPED',
                {'new': pygame.CONTROLLERDEVICEREMAPPED},
            ),
            # Drop events
            'DROPBEGIN': ('pygame.DROPBEGIN', {'new': pygame.DROPBEGIN}),
            'DROPCOMPLETE': ('pygame.DROPCOMPLETE', {'new': pygame.DROPCOMPLETE}),
            'DROPFILE': ('pygame.DROPFILE', {'new': pygame.DROPFILE}),
            'DROPTEXT': ('pygame.DROPTEXT', {'new': pygame.DROPTEXT}),
            # MIDI events
            'MIDIIN': ('pygame.MIDIIN', {'new': pygame.MIDIIN}),
            # User events
            'USEREVENT': ('pygame.USEREVENT', {'new': pygame.USEREVENT}),
        }

    @staticmethod
    def _build_patch_definitions():
        """Build the shared patch definitions used by both setup methods.

        Creates all mock objects and closures, then returns a dict mapping
        patch names to (target, patch_kwargs) tuples that can be applied
        via either unittest.mock.patch() or mocker.patch().

        Returns:
            dict: Mapping of patch name to (target_string, kwargs_dict).

        """
        mock_objects = MockFactory._create_mock_objects()
        patch_definitions = MockFactory._build_core_patch_definitions(mock_objects)
        patch_definitions.update(MockFactory._build_event_constant_patches())
        return patch_definitions

    @staticmethod
    def setup_pygame_mocks():
        """Set up comprehensive pygame mocks for testing.

        Returns:
            dict: A dictionary of patch names to their patcher objects.
                  Each patcher is NOT yet started - callers must start them.

        """
        patch_definitions = MockFactory._build_patch_definitions()
        patchers = {}
        for name, (target, kwargs) in patch_definitions.items():
            patchers[name] = patch(target, **kwargs)
        return patchers

    @staticmethod
    def teardown_pygame_mocks(patchers):
        """Tear down pygame mocks to prevent test interference.

        Args:
            patchers: Dict of patchers returned by setup_pygame_mocks().

        """
        for patcher in patchers.values():
            patcher.stop()

    @staticmethod
    def setup_pygame_mocks_with_mocker(mocker):
        """Set up comprehensive pygame mocks using pytest-mock's mocker fixture.

        Unlike setup_pygame_mocks(), this method uses mocker.patch() which
        automatically cleans up all patches at test teardown. No manual
        teardown_pygame_mocks() call is needed.

        Args:
            mocker: The pytest-mock mocker fixture.

        Returns:
            dict: A dictionary of mock names to their mock objects for inspection.

        """
        patch_definitions = MockFactory._build_patch_definitions()
        mocks = {}
        for name, (target, kwargs) in patch_definitions.items():
            mocks[name] = mocker.patch(target, **kwargs)
        return mocks


# Convenience functions for common use cases
def create_8x8_sprite_mock(animation_name: str = 'idle') -> Mock:
    """Create a standard 8x8 sprite mock.

    Returns:
        Mock: The newly created 8x8 sprite mock.

    """
    return MockFactory.create_animated_sprite_mock(
        config=MockSpriteConfig(animation_name=animation_name, frame_size=(8, 8)),
    )


def create_10x10_sprite_mock(animation_name: str = 'idle') -> Mock:
    """Create a 10x10 sprite mock for dimension testing.

    Returns:
        Mock: The newly created 10x10 sprite mock.

    """
    return MockFactory.create_animated_sprite_mock(
        config=MockSpriteConfig(animation_name=animation_name, frame_size=(10, 10)),
    )


def create_custom_sprite_mock(
    animation_name: str,
    frame_size: tuple,
    pixel_color: tuple = (255, 0, 0),
) -> Mock:
    """Create a custom sprite mock with specified parameters.

    Returns:
        Mock: The newly created custom sprite mock.

    """
    return MockFactory.create_animated_sprite_mock(
        config=MockSpriteConfig(
            animation_name=animation_name,
            frame_size=frame_size,
            pixel_color=pixel_color,
        ),
    )


# Template-related mock functions
def create_template_path_mock(template_name: str = 'test_template') -> Mock:
    """Create a mock Path object for template testing.

    Returns:
        Mock: The newly created template path mock.

    """
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
            return f'/mock/path/{self._template_name}'

        def __repr__(self):
            return f"MockPath('{self._template_name}')"

    return MockPath(template_name)  # type: ignore[invalid-return-type]


def create_template_repo_file_mock(repo_url: str | None = None) -> Mock:
    """Create a mock .repo file for template testing.

    Returns:
        Mock: The newly created template repo file mock.

    """
    mock_file = Mock()
    mock_file.__enter__ = Mock(return_value=mock_file)
    mock_file.__exit__ = Mock(return_value=None)
    if repo_url:
        mock_file.readline.return_value = repo_url
    else:
        mock_file.readline.side_effect = FileNotFoundError()
    return mock_file


def create_template_directory_mock(template_names: list | None = None) -> Mock:
    """Create a mock template directory with specified templates.

    Returns:
        Mock: The newly created template directory mock.

    """
    if template_names is None:
        template_names = ['template1', 'template2']

    mock_items = []
    for name in template_names:
        mock_item = Mock()
        mock_item.name = name
        mock_items.append(mock_item)

    mock_path = Mock()
    mock_path.iterdir.return_value = mock_items
    return mock_path
