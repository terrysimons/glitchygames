"""Centralized mock factory for test objects.

This module provides reusable mock factories for creating consistent test objects
across all test files, reducing code duplication and ensuring proper mock configuration.
"""

from unittest.mock import Mock, patch
import pygame

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
        mock_frame.get_width.return_value = frame_size[0]
        mock_frame.get_height.return_value = frame_size[1]
        # Calculate pixel count and create pixel data
        pixel_count = frame_size[0] * frame_size[1]
        mock_frame.get_pixel_data.return_value = [pixel_color] * pixel_count
        
        # Create frame image with proper methods
        mock_frame_image = Mock()
        mock_frame_image.get_width.return_value = frame_size[0]
        mock_frame_image.get_height.return_value = frame_size[1]
        mock_frame.image = mock_frame_image
        
        # Add duration attribute for animation timing
        mock_frame.duration = 1.0  # 1 second duration

        # Configure sprite properties
        # Create multiple frames for testing (3 frames per animation)
        mock_frames = []
        for i in range(3):  # Create 3 frames
            frame = Mock()
            frame.get_size.return_value = frame_size
            frame.get_width.return_value = frame_size[0]
            frame.get_height.return_value = frame_size[1]
            frame.get_pixel_data.return_value = [pixel_color] * pixel_count
            
            # Create frame image with proper methods
            frame_image = Mock()
            frame_image.get_width.return_value = frame_size[0]
            frame_image.get_height.return_value = frame_size[1]
            frame.image = frame_image
            
            # Add duration attribute for animation timing
            frame.duration = 1.0  # 1 second duration
            mock_frames.append(frame)
        
        mock_sprite._animations = {animation_name: mock_frames}
        mock_sprite.current_animation = ""  # Start with empty animation
        mock_sprite.current_frame = 0  # Start with frame 0
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
        
        def mock_set_animation(animation_name):
            mock_sprite.current_animation = animation_name
        mock_sprite.set_animation = mock_set_animation
        
        def mock_set_frame(frame_idx):
            mock_sprite.current_frame = frame_idx
        mock_sprite.set_frame = mock_set_frame
        
        def mock_get_pixel_data():
            # Return pixel data for the current frame
            current_anim = mock_sprite.current_animation
            current_frame = mock_sprite.current_frame
            if current_anim in mock_sprite._animations and current_frame < len(mock_sprite._animations[current_anim]):
                frame = mock_sprite._animations[current_anim][current_frame]
                return frame.get_pixel_data()
            return [pixel_color] * pixel_count
        mock_sprite.get_pixel_data = mock_get_pixel_data
        
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
        
        # Add pixel manipulation methods
        surface.set_at.return_value = None
        surface.get_at.return_value = (0, 0, 0, 255)

        # Rect mock supports attribute mutation in tests
        def mock_get_rect(x=0, y=0, **kwargs):
            """Mock get_rect that properly handles x, y positioning."""
            rect = Mock()
            rect.x = x
            rect.y = y
            rect.width = width
            rect.height = height
            rect.top = y
            rect.bottom = y + height
            rect.left = x
            rect.right = x + width
            rect.center = (x + width // 2, y + height // 2)
            return rect
        
        surface.get_rect = mock_get_rect
        
        return surface

    @staticmethod
    def create_real_pygame_surface(width: int = 8, height: int = 8):
        """Create a real pygame.Surface for tests that need actual pygame functionality."""
        import pygame
        # Initialize pygame if not already initialized
        if not pygame.get_init():
            pygame.init()
        return pygame.Surface((width, height))

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
                    if isinstance(args[0], (tuple, list)) and len(args[0]) >= 2:
                        width, height = args[0][0], args[0][1]
                    elif len(args) >= 2:
                        width, height = args[0], args[1]
                    else:
                        width, height = 32, 32  # Default size
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
        
        # Add pixel manipulation methods
        screen.set_at.return_value = None
        screen.get_at.return_value = (0, 0, 0, 255)
        
        return screen

    @staticmethod
    def _mock_sprite_init(self, *args, **kwargs):
        """Mock Sprite.__init__ that handles pygame.display.get_surface() properly."""
        # Avoid referencing self in debug output to prevent __str__ access before attributes are set
        # Extract arguments from kwargs since that's how they're being passed
        x = kwargs.get("x", 0)
        y = kwargs.get("y", 0)
        width = kwargs.get("width", 32)
        height = kwargs.get("height", 32)
        name = kwargs.get("name", "")
        parent = kwargs.get("parent", None)
        groups = kwargs.get("groups", None)
        
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
        
        # For ButtonSprite, we need to ensure that when TextSprite is created, it has the right attributes
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
        # that might reference attributes not yet initialized (e.g., ButtonSprite.x setter references self.text)
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
        display_mock.get_surface.return_value = MockFactory.create_display_mock()
        display_mock.set_mode.return_value = MockFactory.create_display_mock()
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
    def setup_pygame_mocks():
        """Set up comprehensive pygame mocks for testing.

        Returns:
            tuple: (display_patcher, surface_patcher, event_patcher, ...)

        """
        # Create comprehensive mocks
        display_mock = MockFactory.create_pygame_display_mock()

        # Set up patches
        display_patcher = patch("pygame.display", display_mock)
        # Also patch pygame.display.get_surface directly to ensure it returns a proper mock
        display_get_surface_patcher = patch("pygame.display.get_surface", return_value=MockFactory.create_display_mock())
        
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
        
        # Draw function mocking - create mocks that handle MockSurface objects
        import pygame
        original_draw_polygon = pygame.draw.polygon
        
        def mock_draw_polygon(surface, color, points, width=0):
            """Mock pygame.draw.polygon that handles MockSurface objects."""
            if hasattr(surface, '_surface'):
                # Use the original pygame.draw.polygon directly to avoid recursion
                return original_draw_polygon(surface._surface, color, points, width)
            else:
                return original_draw_polygon(surface, color, points, width)
        
        draw_polygon_patcher = patch("pygame.draw.polygon", side_effect=mock_draw_polygon)
        
        # Sound/mixer mocking
        mixer_mock = Mock()
        mixer_mock.Sound.return_value = Mock()
        mixer_patcher = patch("pygame.mixer", mixer_mock)
        mixer_sound_patcher = patch("pygame.mixer.Sound", return_value=Mock())
        
        # Keyboard mocking
        key_mock = Mock()
        key_mock.set_repeat.return_value = None
        key_patcher = patch("pygame.key", key_mock)
        
        # Transform mocking - create a mock that returns a real surface
        def mock_transform_scale(surface, size):
            """Mock pygame.transform.scale that returns a real surface."""
            import pygame
            return pygame.Surface(size)
        transform_scale_patcher = patch("pygame.transform.scale", side_effect=mock_transform_scale)
        
        # Surface mocking - create real surfaces for drawing operations
        class MockSurface:
            """Wrapper around pygame.Surface that provides mockable convert methods."""
            def __init__(self, *args, **kwargs):
                import pygame
                if not pygame.get_init():
                    pygame.init()
                self._surface = pygame.surface.Surface(*args, **kwargs)
                # Copy all attributes from the real surface
                for attr in dir(self._surface):
                    if not attr.startswith("_") and not callable(getattr(self._surface, attr)):
                        setattr(self, attr, getattr(self._surface, attr))
            
            def __getattr__(self, name):
                """Delegate attribute access to the real surface."""
                return getattr(self._surface, name)
            
            def convert(self, *args, **kwargs):
                """Mock convert method that returns self."""
                return self
            
            def convert_alpha(self, *args, **kwargs):
                """Mock convert_alpha method that returns self."""
                return self
            
            def blit(self, source, dest, area=None, special_flags=0):
                """Delegate blit to the real surface."""
                # Handle MockSurface sources by extracting their real surface
                if hasattr(source, '_surface'):
                    source = source._surface
                return self._surface.blit(source, dest, area, special_flags)
            
            def fill(self, color, rect=None, special_flags=0):
                """Delegate fill to the real surface."""
                return self._surface.fill(color, rect, special_flags)
            
            def get_rect(self, **kwargs):
                """Delegate get_rect to the real surface."""
                return self._surface.get_rect(**kwargs)
        
        def mock_surface_constructor(*args, **kwargs):
            """Mock pygame.Surface constructor that returns a MockSurface."""
            return MockSurface(*args, **kwargs)
        surface_constructor_patcher = patch("pygame.Surface", side_effect=mock_surface_constructor)
        
        # FontManager mock - create a mock font that returns a proper surface
        mock_font = Mock()
        
        # Create a mock surface for text rendering that handles all render signatures
        def mock_render(*args, **kwargs):
            # Handle different render method signatures
            if len(args) >= 1:
                text = str(args[0])
            else:
                text = "Mock"
            
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
            surface.get_rect = Mock(return_value=text_rect)
            
            # Handle different return types (surface vs (surface, rect))
            if 'fgcolor' in kwargs or len(args) >= 2:
                # pygame.freetype style - return (surface, rect)
                return surface, text_rect
            else:
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
            # Return mock pixel data based on surface size
            if hasattr(surface, "get_width") and hasattr(surface, "get_height"):
                width = surface.get_width()
                height = surface.get_height()
                
                # Check if this is a single-color surface (for legacy sprite tests)
                # If the surface has a single color, return consistent pixel data
                if hasattr(surface, "_test_single_color") and surface._test_single_color:
                    # Return all pixels as red (255, 0, 0) for single color tests
                    pixel_data = bytearray()
                    for y in range(height):
                        for x in range(width):
                            pixel_data.extend([255, 0, 0])  # Red color
                    return bytes(pixel_data)
                else:
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
        
        # Sprite class mocking - patch the BitmappySprite constructor to handle pygame.display.get_surface()
        sprite_patcher = patch("glitchygames.sprites.BitmappySprite.__init__", MockFactory._mock_sprite_init)
        
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

        return (display_patcher, display_get_surface_patcher, surface_patcher, event_patcher, event_blocked_patcher,
                event_post_patcher, event_event_patcher, draw_circle_patcher, draw_line_patcher, 
                draw_rect_patcher, draw_polygon_patcher, mixer_patcher, mixer_sound_patcher, key_patcher, transform_scale_patcher, surface_constructor_patcher, image_tostring_patcher, font_manager_patcher, clock_patcher,
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
        (display_patcher, display_get_surface_patcher, surface_patcher, event_patcher, event_blocked_patcher,
         event_post_patcher, event_event_patcher, draw_circle_patcher, draw_line_patcher,
         draw_rect_patcher, draw_polygon_patcher, mixer_patcher, mixer_sound_patcher, key_patcher, transform_scale_patcher, surface_constructor_patcher, image_tostring_patcher, font_manager_patcher, clock_patcher,
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
        transform_scale_patcher.stop()
        surface_constructor_patcher.stop()
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


def create_template_repo_file_mock(repo_url: str = None) -> Mock:
    """Create a mock .repo file for template testing."""
    mock_file = Mock()
    mock_file.__enter__ = Mock(return_value=mock_file)
    mock_file.__exit__ = Mock(return_value=None)
    if repo_url:
        mock_file.readline.return_value = repo_url
    else:
        mock_file.readline.side_effect = FileNotFoundError()
    return mock_file


def create_template_directory_mock(template_names: list = None) -> Mock:
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
