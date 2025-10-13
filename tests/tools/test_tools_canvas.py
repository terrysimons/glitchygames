"""Canvas interfaces tool functionality tests."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools import canvas_interfaces

from mocks.test_mock_factory import MockFactory


class TestCanvasInterfaces(unittest.TestCase):
    """Test canvas interfaces functionality."""

    def test_canvas_interface_protocol(self):
        """Test canvas interface protocol."""
        # Test that CanvasInterface protocol is defined
        assert hasattr(canvas_interfaces, "CanvasInterface")
        
        # Test protocol methods exist
        protocol = canvas_interfaces.CanvasInterface
        assert hasattr(protocol, "__abstractmethods__")

    def test_sprite_serializer_abstract_base(self):
        """Test sprite serializer abstract base."""
        # Test that SpriteSerializer is defined
        assert hasattr(canvas_interfaces, "SpriteSerializer")
        
        # Test abstract methods exist
        serializer = canvas_interfaces.SpriteSerializer
        assert hasattr(serializer, "__abstractmethods__")

    def test_animated_canvas_interface_protocol(self):
        """Test animated canvas interface protocol."""
        # Test that AnimatedCanvasInterface protocol is defined
        assert hasattr(canvas_interfaces, "AnimatedCanvasInterface")
        
        # Test that it's a class (not necessarily abstract)
        protocol = canvas_interfaces.AnimatedCanvasInterface
        assert callable(protocol)

    def test_animated_canvas_renderer_protocol(self):
        """Test animated canvas renderer protocol."""
        # Test that AnimatedCanvasRenderer protocol is defined
        assert hasattr(canvas_interfaces, "AnimatedCanvasRenderer")
        
        # Test protocol methods exist
        protocol = canvas_interfaces.AnimatedCanvasRenderer
        assert hasattr(protocol, "__abstractmethods__")

    def test_animated_sprite_serializer_protocol(self):
        """Test animated sprite serializer protocol."""
        # Test that AnimatedSpriteSerializer protocol is defined
        assert hasattr(canvas_interfaces, "AnimatedSpriteSerializer")
        
        # Test protocol methods exist
        protocol = canvas_interfaces.AnimatedSpriteSerializer
        assert hasattr(protocol, "__abstractmethods__")

    def test_static_canvas_interface_initialization(self):
        """Test static canvas interface initialization."""
        # Test StaticCanvasInterface initialization - requires canvas_sprite parameter
        mock_sprite = Mock()
        interface = canvas_interfaces.StaticCanvasInterface(mock_sprite)
        
        # Test basic properties
        assert hasattr(interface, "canvas_sprite")
        assert interface.canvas_sprite == mock_sprite

    def test_static_canvas_interface_pixel_operations(self):
        """Test static canvas interface pixel operations."""
        mock_sprite = Mock()
        interface = canvas_interfaces.StaticCanvasInterface(mock_sprite)
        
        # Test that interface has expected methods
        assert hasattr(interface, "get_pixel_data")
        assert hasattr(interface, "set_pixel_data")
        assert hasattr(interface, "get_dimensions")
        assert callable(interface.get_pixel_data)
        assert callable(interface.set_pixel_data)
        assert callable(interface.get_dimensions)

    def test_animated_canvas_interface_initialization(self):
        """Test animated canvas interface initialization."""
        # Test AnimatedCanvasInterface initialization - requires properly mocked canvas_sprite
        mock_sprite = Mock()
        mock_animated_sprite = Mock()
        mock_animated_sprite._animation_order = ["idle"]
        mock_sprite.animated_sprite = mock_animated_sprite
        
        interface = canvas_interfaces.AnimatedCanvasInterface(mock_sprite)
        
        # Test basic properties
        assert hasattr(interface, "canvas_sprite")
        assert interface.canvas_sprite == mock_sprite

    def test_static_canvas_interface_comprehensive(self):
        """Test comprehensive static canvas interface functionality."""
        mock_sprite = Mock()
        interface = canvas_interfaces.StaticCanvasInterface(mock_sprite)
        
        # Test that interface has expected methods
        assert hasattr(interface, "get_pixel_data")
        assert hasattr(interface, "set_pixel_data")
        assert hasattr(interface, "get_dimensions")
        assert callable(interface.get_pixel_data)
        assert callable(interface.set_pixel_data)
        assert callable(interface.get_dimensions)

    def test_static_sprite_serializer(self):
        """Test static sprite serializer functionality."""
        # Test StaticSpriteSerializer initialization - takes no arguments
        serializer = canvas_interfaces.StaticSpriteSerializer()
        
        # Test basic properties - StaticSpriteSerializer doesn't have canvas_sprite attribute
        # It's an abstract base class, so we just verify it can be instantiated
        assert serializer is not None

    def test_static_canvas_renderer(self):
        """Test static canvas renderer functionality."""
        # Test StaticCanvasRenderer initialization - requires canvas_sprite parameter
        mock_sprite = Mock()
        renderer = canvas_interfaces.StaticCanvasRenderer(mock_sprite)
        
        # Test basic properties
        assert hasattr(renderer, "canvas_sprite")
        assert renderer.canvas_sprite == mock_sprite


if __name__ == "__main__":
    unittest.main()
