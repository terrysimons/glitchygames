"""Centralized mock factory for test objects.

This module provides reusable mock factories for creating consistent test objects
across all test files, reducing code duplication and ensuring proper mock configuration.
"""

from unittest.mock import Mock, patch

from glitchygames.sprites import AnimatedSprite


class MockFactory:
    """Factory class for creating properly configured mock objects."""

    @staticmethod
    def create_animated_sprite_mock(
        animation_name: str = "idle",
        frame_size: tuple = (8, 8),
        pixel_color: tuple = (255, 0, 0),
        current_frame: int = 0,
        *,
        is_playing: bool = False,
        is_looping: bool = True
    ) -> Mock:
        """Create a properly configured AnimatedSprite mock.

        Args:
            animation_name: Name of the animation (default: "idle")
            frame_size: Size of the frame as (width, height) (default: (8, 8))
            pixel_color: RGB color tuple for pixels (default: (255, 0, 0))
            current_frame: Current frame index (default: 0)
            is_playing: Whether animation is playing (default: False)
            is_looping: Whether animation is looping (default: True)

        Returns:
            Properly configured AnimatedSprite mock

        """
        # Create the mock sprite
        mock_sprite = Mock(spec=AnimatedSprite)

        # Create properly configured frame
        mock_frame = Mock()
        mock_frame.get_size.return_value = frame_size
        # Calculate pixel count and create pixel data
        pixel_count = frame_size[0] * frame_size[1]
        mock_frame.get_pixel_data.return_value = [pixel_color] * pixel_count

        # Configure sprite properties
        mock_sprite._animations = {animation_name: [mock_frame]}
        mock_sprite._animation_order = [animation_name]
        mock_sprite.current_animation = animation_name
        mock_sprite.current_frame = current_frame
        mock_sprite.is_playing = is_playing
        mock_sprite._is_looping = is_looping

        # Add frames attribute that canvas_interfaces.py expects
        mock_sprite.frames = {animation_name: [mock_frame]}
        
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
        
        mock_sprite.get_current_surface = Mock(return_value=Mock())
        mock_sprite.save = Mock()
        mock_sprite.load = Mock()
        
        # Add missing attributes
        mock_sprite._surface_cache = {}
        mock_sprite._frame_manager = Mock()
        mock_sprite._frame_manager._observers = []
        mock_sprite._frame_manager.animated_sprite = mock_sprite

        return mock_sprite

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
    def create_pygame_surface_mock(width: int = 8, height: int = 8) -> Mock:
        """Create a pygame.Surface-like mock suitable for Sprite tests."""
        # Create a mock that will be recognized as a pygame.Surface instance
        surface = Mock()
        surface.convert.return_value = surface
        surface.convert_alpha.return_value = surface
        surface.set_colorkey.return_value = None
        surface.get_size.return_value = (width, height)
        surface.get_width.return_value = width
        surface.get_height.return_value = height
        surface.get_pixel_data.return_value = [(255, 0, 0)] * (width * height)
        
        # Add fill method that UI dialogs need
        surface.fill.return_value = None
        
        # Add blit method for surface operations
        surface.blit.return_value = None
        
        # Add copy method
        surface.copy.return_value = surface

        # Rect mock supports attribute mutation in tests
        rect = Mock()
        rect.x = 0
        rect.y = 0
        rect.width = width
        rect.height = height
        rect.top = 0
        rect.bottom = height
        rect.left = 0
        rect.right = width
        rect.center = (width // 2, height // 2)
        surface.get_rect.return_value = rect
        
        return surface

    @staticmethod
    def create_pygame_surface_class_mock():
        """Create a pygame.Surface class mock that works with isinstance checks."""
        # Create a mock class that can be used with isinstance
        class MockSurfaceClass:
            def __init__(self, *args, **kwargs):
                # Return a properly configured surface mock
                self._mock_surface = MockFactory.create_pygame_surface_mock()
                # Copy all attributes from the mock surface
                for attr in dir(self._mock_surface):
                    if not attr.startswith('_'):
                        setattr(self, attr, getattr(self._mock_surface, attr))
        
        # Make it look like a proper class
        MockSurfaceClass.__name__ = "Surface"
        MockSurfaceClass.__module__ = "pygame"
        
        # Store the class for isinstance checks
        MockFactory._surface_class = MockSurfaceClass
        
        return MockSurfaceClass

    @staticmethod
    def create_display_mock(width: int = 800, height: int = 600) -> Mock:
        """Create a mock for pygame.display.get_surface()."""
        screen = Mock()
        screen.get_width.return_value = width
        screen.get_height.return_value = height
        screen.get_size.return_value = (width, height)
        # Provide a minimal screen rect-like attributes used by paddles
        screen.left = 0
        screen.right = width
        screen.top = 0
        screen.bottom = height
        
        # Add get_rect method that returns a mock with center attribute
        rect_mock = Mock()
        rect_mock.center = (width // 2, height // 2)
        screen.get_rect.return_value = rect_mock
        
        return screen

    @staticmethod
    def _mock_sprite_init(sprite_instance, x=0, y=0, width=32, height=32, name="", parent=None, groups=None):
        """Mock Sprite.__init__ that handles pygame.display.get_surface() properly."""
        # Set basic attributes
        sprite_instance.x = x
        sprite_instance.y = y
        sprite_instance.width = width
        sprite_instance.height = height
        sprite_instance.name = name
        sprite_instance.parent = parent
        sprite_instance.groups = groups or []
        
        # Mock screen with proper methods
        sprite_instance.screen = MockFactory.create_display_mock()
        sprite_instance.screen_width = sprite_instance.screen.get_width()
        sprite_instance.screen_height = sprite_instance.screen.get_height()
        
        # Mock other sprite attributes
        sprite_instance.image = Mock()
        sprite_instance.rect = Mock()
        sprite_instance.rect.x = x
        sprite_instance.rect.y = y
        sprite_instance.rect.width = width
        sprite_instance.rect.height = height
        sprite_instance.rect.center = (x + width // 2, y + height // 2)
        sprite_instance.rect.left = x
        sprite_instance.rect.right = x + width
        sprite_instance.rect.top = y
        sprite_instance.rect.bottom = y + height
        
        sprite_instance.dirty = 1
        sprite_instance.visible = 1

    @staticmethod
    def create_pygame_display_mock() -> Mock:
        """Create a comprehensive pygame.display mock with initialization."""
        display_mock = Mock()
        display_mock.init.return_value = None
        display_mock.quit.return_value = None
        display_mock.get_surface.return_value = MockFactory.create_display_mock()
        display_mock.set_mode.return_value = MockFactory.create_display_mock()
        display_mock.flip.return_value = None
        display_mock.update.return_value = None
        display_mock.set_icon.return_value = None
        display_mock.get_caption.return_value = ("Test Game", "Test Game")
        return display_mock

    @staticmethod
    def setup_pygame_mocks():
        """Set up comprehensive pygame mocks for testing.

        Returns:
            tuple: (display_patcher, surface_patcher, event_patcher, ...)

        """
        # Create comprehensive mocks
        display_mock = MockFactory.create_pygame_display_mock()

        # Set up patches
        display_patcher = patch("pygame.display", display_mock)
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
        transform_scale_patcher = patch("pygame.transform.scale")
        
        # FontManager mock - create a mock font that returns a mock surface
        mock_font = Mock()
        mock_font.render = Mock(return_value=Mock())
        font_manager_patcher = patch("glitchygames.fonts.FontManager.get_font", return_value=mock_font)

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
        
        # Sprite class mocking - patch the Sprite constructor to handle pygame.display.get_surface()
        sprite_patcher = patch("glitchygames.sprites.Sprite.__init__", side_effect=MockFactory._mock_sprite_init)
        
        # Key constants mocking
        key_constants_patcher = patch("pygame.K_q", 113)
        key_escape_patcher = patch("pygame.K_ESCAPE", 27)
        key_down_patcher = patch("pygame.KEYDOWN", 2)
        key_up_patcher = patch("pygame.KEYUP", 3)
        mouse_button_down_patcher = patch("pygame.MOUSEBUTTONDOWN", 5)
        mouse_button_up_patcher = patch("pygame.MOUSEBUTTONUP", 6)
        mouse_motion_patcher = patch("pygame.MOUSEMOTION", 4)
        mouse_wheel_patcher = patch("pygame.MOUSEWHEEL", 7)
        quit_event_patcher = patch("pygame.QUIT", 256)
        text_input_patcher = patch("pygame.TEXTINPUT", 771)
        touch_down_patcher = patch("pygame.FINGERDOWN", 1024)
        touch_up_patcher = patch("pygame.FINGERUP", 1025)
        touch_motion_patcher = patch("pygame.FINGERMOTION", 1026)
        window_resized_patcher = patch("pygame.WINDOWRESIZED", 32768)
        window_restored_patcher = patch("pygame.WINDOWRESTORED", 32769)
        window_focus_gained_patcher = patch("pygame.WINDOWFOCUSGAINED", 32770)
        window_focus_lost_patcher = patch("pygame.WINDOWFOCUSLOST", 32771)
        audio_device_added_patcher = patch("pygame.AUDIODEVICEADDED", 32784)
        audio_device_removed_patcher = patch("pygame.AUDIODEVICEREMOVED", 32785)
        
        # Joystick/Controller events
        joystick_axis_motion_patcher = patch("pygame.JOYAXISMOTION", 7)
        joystick_ball_motion_patcher = patch("pygame.JOYBALLMOTION", 8)
        joystick_button_down_patcher = patch("pygame.JOYBUTTONDOWN", 9)
        joystick_button_up_patcher = patch("pygame.JOYBUTTONUP", 10)
        joystick_hat_motion_patcher = patch("pygame.JOYHATMOTION", 11)
        joystick_device_added_patcher = patch("pygame.JOYDEVICEADDED", 11)
        joystick_device_removed_patcher = patch("pygame.JOYDEVICEREMOVED", 12)
        
        # Controller events
        controller_axis_motion_patcher = patch("pygame.CONTROLLERAXISMOTION", 11)
        controller_button_down_patcher = patch("pygame.CONTROLLERBUTTONDOWN", 12)
        controller_button_up_patcher = patch("pygame.CONTROLLERBUTTONUP", 13)
        controller_device_added_patcher = patch("pygame.CONTROLLERDEVICEADDED", 13)
        controller_device_removed_patcher = patch("pygame.CONTROLLERDEVICEREMOVED", 14)
        controller_device_remapped_patcher = patch("pygame.CONTROLLERDEVICEREMAPPED", 15)
        
        # Drop events
        drop_begin_patcher = patch("pygame.DROPBEGIN", 4096)
        drop_complete_patcher = patch("pygame.DROPCOMPLETE", 4097)
        drop_file_patcher = patch("pygame.DROPFILE", 4098)
        drop_text_patcher = patch("pygame.DROPTEXT", 4099)
        
        # MIDI events
        midi_in_patcher = patch("pygame.MIDIIN", 32786)
        
        # User events
        user_event_patcher = patch("pygame.USEREVENT", 24)
        
        # Return patchers without starting them - let the test files start them

        return (display_patcher, surface_patcher, event_patcher, event_blocked_patcher,
                event_post_patcher, event_event_patcher, draw_circle_patcher, draw_line_patcher, 
                draw_rect_patcher, transform_scale_patcher, font_manager_patcher, clock_patcher,
                sprite_patcher, key_constants_patcher, key_escape_patcher, key_down_patcher, key_up_patcher,
                mouse_button_down_patcher, mouse_button_up_patcher, mouse_motion_patcher,
                mouse_wheel_patcher, quit_event_patcher, text_input_patcher, touch_down_patcher,
                touch_up_patcher, touch_motion_patcher, window_resized_patcher, window_restored_patcher,
                window_focus_gained_patcher, window_focus_lost_patcher, audio_device_added_patcher,
                audio_device_removed_patcher, joystick_axis_motion_patcher, joystick_ball_motion_patcher,
                joystick_button_down_patcher, joystick_button_up_patcher, joystick_hat_motion_patcher,
                joystick_device_added_patcher, joystick_device_removed_patcher, controller_axis_motion_patcher,
                controller_button_down_patcher, controller_button_up_patcher, controller_device_added_patcher,
                controller_device_removed_patcher, controller_device_remapped_patcher, drop_begin_patcher,
                drop_complete_patcher, drop_file_patcher, drop_text_patcher, midi_in_patcher, user_event_patcher)

    @staticmethod
    def teardown_pygame_mocks(patchers):
        """Tear down pygame mocks to prevent test interference.

        Args:
            patchers: Tuple of patchers returned by setup_pygame_mocks()

        """
        (display_patcher, surface_patcher, event_patcher, event_blocked_patcher,
         event_post_patcher, event_event_patcher, draw_circle_patcher, draw_line_patcher, 
         draw_rect_patcher, transform_scale_patcher, font_manager_patcher, clock_patcher,
         sprite_patcher, key_constants_patcher, key_escape_patcher, key_down_patcher, key_up_patcher,
         mouse_button_down_patcher, mouse_button_up_patcher, mouse_motion_patcher,
         mouse_wheel_patcher, quit_event_patcher, text_input_patcher, touch_down_patcher,
         touch_up_patcher, touch_motion_patcher, window_resized_patcher, window_restored_patcher,
         window_focus_gained_patcher, window_focus_lost_patcher, audio_device_added_patcher,
         audio_device_removed_patcher, joystick_axis_motion_patcher, joystick_ball_motion_patcher,
         joystick_button_down_patcher, joystick_button_up_patcher, joystick_hat_motion_patcher,
         joystick_device_added_patcher, joystick_device_removed_patcher, controller_axis_motion_patcher,
         controller_button_down_patcher, controller_button_up_patcher, controller_device_added_patcher,
         controller_device_removed_patcher, controller_device_remapped_patcher, drop_begin_patcher,
         drop_complete_patcher, drop_file_patcher, drop_text_patcher, midi_in_patcher, user_event_patcher) = patchers
        
        # Stop all patches
        display_patcher.stop()
        surface_patcher.stop()
        event_patcher.stop()
        event_blocked_patcher.stop()
        event_post_patcher.stop()
        event_event_patcher.stop()
        draw_circle_patcher.stop()
        draw_line_patcher.stop()
        draw_rect_patcher.stop()
        transform_scale_patcher.stop()
        font_manager_patcher.stop()
        clock_patcher.stop()
        sprite_patcher.stop()
        
        # Stop all constant patches
        key_constants_patcher.stop()
        key_escape_patcher.stop()
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
