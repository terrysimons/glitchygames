"""Centralized mock factory for test objects.

This module provides reusable mock factories for creating consistent test objects
across all test files, reducing code duplication and ensuring proper mock configuration.
"""

from unittest.mock import Mock
from glitchygames.sprites import AnimatedSprite


class MockFactory:
    """Factory class for creating properly configured mock objects."""
    
    @staticmethod
    def create_animated_sprite_mock(
        animation_name: str = "idle",
        frame_size: tuple = (8, 8),
        pixel_color: tuple = (255, 0, 0),
        current_frame: int = 0,
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
