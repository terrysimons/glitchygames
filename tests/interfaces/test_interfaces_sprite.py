"""Test coverage for SpriteInterface."""

import inspect
import typing
from unittest.mock import Mock

import pygame
from glitchygames.interfaces import SpriteInterface

# Suppress PLR6301 for test methods (they need self for fixtures)
# ruff: noqa: PLR6301


class TestSpriteInterface:
    """Test coverage for SpriteInterface class."""

    def test_sprite_interface_instantiation(self):
        """Test that SpriteInterface can be instantiated."""
        sprite = SpriteInterface()
        assert isinstance(sprite, SpriteInterface)

    def test_sprite_interface_update_nested_sprites(self):
        """Test update_nested_sprites method."""
        sprite = SpriteInterface()
        # Should not raise any exception
        sprite.update_nested_sprites()

    def test_sprite_interface_update(self):
        """Test update method."""
        sprite = SpriteInterface()
        # Should not raise any exception
        sprite.update()

    def test_sprite_interface_render(self):
        """Test render method."""
        sprite = SpriteInterface()
        mock_screen = Mock(spec=pygame.Surface)
        # Should not raise any exception
        sprite.render(mock_screen)

    def test_sprite_interface_inheritance(self):
        """Test that SpriteInterface can be inherited."""
        class TestSprite(SpriteInterface):
            def update_nested_sprites(self):
                pass

            def update(self):
                pass

            def render(self, screen):
                pass

        sprite = TestSprite()
        assert isinstance(sprite, SpriteInterface)
        assert isinstance(sprite, TestSprite)

    def test_sprite_interface_method_signatures(self):
        """Test that SpriteInterface methods have correct signatures."""
        # Check update_nested_sprites signature
        update_nested_sprites_sig = inspect.signature(SpriteInterface.update_nested_sprites)
        assert len(update_nested_sprites_sig.parameters) == 1  # self

        # Check update signature
        update_sig = inspect.signature(SpriteInterface.update)
        assert len(update_sig.parameters) == 1  # self

        # Check render signature
        render_sig = inspect.signature(SpriteInterface.render)
        assert len(render_sig.parameters) == 2  # self, screen
        assert "screen" in render_sig.parameters

    def test_sprite_interface_method_return_types(self):
        """Test that SpriteInterface methods have correct return type annotations."""
        # Check update_nested_sprites return type
        update_nested_sprites_annotations = SpriteInterface.update_nested_sprites.__annotations__
        assert "return" in update_nested_sprites_annotations
        assert update_nested_sprites_annotations["return"] == "None"

        # Check update return type
        update_annotations = SpriteInterface.update.__annotations__
        assert "return" in update_annotations
        assert update_annotations["return"] == "None"

        # Check render return type
        render_annotations = SpriteInterface.render.__annotations__
        assert "return" in render_annotations
        assert render_annotations["return"] == "None"

    def test_type_annotations_with_pygame_surface(self):
        """Test that type annotations work correctly with pygame.Surface."""
        # This test ensures that the TYPE_CHECKING import works correctly
        # and that pygame.Surface is properly typed in the interface
        sprite = SpriteInterface()
        mock_screen = Mock(spec=pygame.Surface)
        
        # This should work without type errors
        sprite.render(mock_screen)
        
        # Verify the method signature includes pygame.Surface
        render_sig = inspect.signature(SpriteInterface.render)
        screen_param = render_sig.parameters["screen"]
        assert screen_param.annotation == "pygame.Surface"
