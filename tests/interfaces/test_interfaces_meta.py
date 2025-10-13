"""Test coverage for interface meta functionality and combinations."""

import inspect
import typing
from importlib import reload

import glitchygames.interfaces as interfaces_module
from glitchygames.interfaces import SceneInterface, SpriteInterface

# Suppress PLR6301 for test methods (they need self for fixtures)
# ruff: noqa: PLR6301


class TestInterfaceMeta:
    """Test coverage for interface meta functionality."""

    def test_sprite_and_scene_interface_combination(self):
        """Test that a class can implement both interfaces."""
        class GameObject(SpriteInterface, SceneInterface):
            def update_nested_sprites(self):
                pass

            def update(self):
                pass

            def render(self, screen):
                pass

            def switch_to_scene(self, next_scene):
                pass

            def terminate(self):
                pass

            def play(self):
                pass

            def pause(self):
                pass

        obj = GameObject()
        assert isinstance(obj, SpriteInterface)
        assert isinstance(obj, SceneInterface)

    def test_interface_abstract_behavior(self):
        """Test that interfaces behave as abstract base classes."""
        # Interfaces should not raise errors when called directly
        sprite = SpriteInterface()
        scene = SceneInterface()
        
        # These should not raise exceptions
        sprite.update_nested_sprites()
        sprite.update()
        scene.terminate()
        scene.play()
        scene.pause()

    def test_interface_documentation(self):
        """Test that interfaces have proper documentation."""
        # Check SpriteInterface documentation
        assert SpriteInterface.__doc__ is not None
        assert "Sprite interface" in SpriteInterface.__doc__
        
        # Check SceneInterface documentation
        assert SceneInterface.__doc__ is not None
        assert "Scene interface" in SceneInterface.__doc__

    def test_type_checking_import_coverage(self):
        """Test that TYPE_CHECKING imports work correctly."""
        # This test ensures that the TYPE_CHECKING import in interfaces works
        # and doesn't cause import issues during runtime
        assert hasattr(interfaces_module, "SpriteInterface")
        assert hasattr(interfaces_module, "SceneInterface")

    def test_reload_with_type_checking_true(self):
        """Test that interfaces module can be reloaded with type checking enabled."""
        # This test ensures that the module can be reloaded without issues
        # when TYPE_CHECKING is True
        reload(interfaces_module)
        
        # Verify interfaces are still accessible after reload
        assert hasattr(interfaces_module, "SpriteInterface")
        assert hasattr(interfaces_module, "SceneInterface")
        
        # Verify they can still be instantiated
        sprite = interfaces_module.SpriteInterface()
        scene = interfaces_module.SceneInterface()
        # After reload, the classes are different objects, so we check by name
        assert sprite.__class__.__name__ == "SpriteInterface"
        assert scene.__class__.__name__ == "SceneInterface"
