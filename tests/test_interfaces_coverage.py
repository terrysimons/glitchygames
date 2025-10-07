"""Test coverage for the interfaces module."""

import inspect
import typing
from importlib import reload
from unittest.mock import Mock

import glitchygames.interfaces as interfaces_module
import pygame
from glitchygames.interfaces import SceneInterface, SpriteInterface

# Suppress PLR6301 for test methods (they need self for fixtures)
# ruff: noqa: PLR6301

# Constants for magic numbers
SIGNATURE_PARAM_COUNT = 2


class TestSpriteInterfaceCoverage:
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


class TestSceneInterfaceCoverage:
    """Test coverage for SceneInterface class."""

    def test_scene_interface_instantiation(self):
        """Test that SceneInterface can be instantiated."""
        scene = SceneInterface()
        assert isinstance(scene, SceneInterface)

    def test_scene_interface_switch_to_scene(self):
        """Test switch_to_scene method."""
        scene = SceneInterface()
        next_scene = SceneInterface()
        # Should not raise any exception
        scene.switch_to_scene(next_scene)

    def test_scene_interface_terminate(self):
        """Test terminate method."""
        scene = SceneInterface()
        # Should not raise any exception
        scene.terminate()

    def test_scene_interface_play(self):
        """Test play method."""
        scene = SceneInterface()
        # Should not raise any exception
        scene.play()

    def test_scene_interface_pause(self):
        """Test pause method."""
        scene = SceneInterface()
        # Should not raise any exception
        scene.pause()


class TestSpriteInterfaceInheritanceCoverage:
    """Test coverage for SpriteInterface inheritance."""

    def test_sprite_interface_inheritance(self):
        """Test that SpriteInterface can be subclassed."""
        class MySprite(SpriteInterface):
            def update(self):
                pass

            def render(self, screen: pygame.Surface):
                pass

        sprite = MySprite()
        assert isinstance(sprite, SpriteInterface)


class TestSceneInterfaceInheritanceCoverage:
    """Test coverage for SceneInterface inheritance."""

    def test_scene_interface_inheritance(self):
        """Test that SceneInterface can be subclassed."""
        class MyScene(SceneInterface):
            def switch_to_scene(self, next_scene: "SceneInterface"):
                pass

            def terminate(self):
                pass

            def play(self):
                pass

            def pause(self):
                pass

        scene = MyScene()
        assert isinstance(scene, SceneInterface)


class TestInterfaceMethodSignaturesCoverage:
    """Test coverage for interface method signatures."""

    def test_sprite_interface_method_signatures(self):
        """Test that SpriteInterface methods have correct signatures."""
        methods = [
            (SpriteInterface.update_nested_sprites, 1),
            (SpriteInterface.update, 1),
            (SpriteInterface.render, SIGNATURE_PARAM_COUNT),
        ]
        for method, expected in methods:
            sig = inspect.signature(method)
            assert len(sig.parameters) == expected

    def test_scene_interface_method_signatures(self):
        """Test that SceneInterface methods have correct signatures."""
        methods = [
            (SceneInterface.switch_to_scene, SIGNATURE_PARAM_COUNT),
            (SceneInterface.terminate, 1),
            (SceneInterface.play, 1),
            (SceneInterface.pause, 1),
        ]
        for method, expected in methods:
            sig = inspect.signature(method)
            assert len(sig.parameters) == expected


class TestInterfacesIntegrationCoverage:
    """Integration tests for interfaces."""

    def test_sprite_and_scene_interface_combination(self):
        """Test that SpriteInterface and SceneInterface can be used together."""
        sprite = SpriteInterface()
        scene = SceneInterface()
        assert isinstance(sprite, SpriteInterface)
        assert isinstance(scene, SceneInterface)

    def test_interface_abstract_behavior(self):
        """Test abstract behavior of the interfaces."""
        sprite = SpriteInterface()
        scene = SceneInterface()
        # Methods should exist and be callable
        assert hasattr(sprite, "render")
        assert hasattr(scene, "switch_to_scene")

    def test_interface_documentation(self):
        """Test that interfaces have documentation strings."""
        assert isinstance(SpriteInterface.__doc__, str)
        assert isinstance(SceneInterface.__doc__, str)

    def test_interface_method_return_types(self):
        """Test that interface methods return None."""
        sprite = SpriteInterface()
        scene = SceneInterface()
        # All interface methods should return None
        assert sprite.update_nested_sprites() is None
        assert sprite.update() is None
        assert sprite.render(Mock(spec=pygame.Surface)) is None
        assert scene.switch_to_scene(SceneInterface()) is None
        assert scene.terminate() is None
        assert scene.play() is None
        assert scene.pause() is None


class TestInterfacesTypeCheckingCoverage:
    """Test coverage for TYPE_CHECKING import in interfaces module."""

    def test_type_checking_import_coverage(self):
        """Test that TYPE_CHECKING import is covered."""
        # Import the module and ensure interfaces are available
        assert hasattr(interfaces_module, "SpriteInterface")
        assert hasattr(interfaces_module, "SceneInterface")

    def test_type_annotations_with_pygame_surface(self):
        """Test type annotations that would reference pygame.Surface."""
        def test_render_function(
            sprite: SpriteInterface, surface: pygame.Surface
        ) -> None:
            """Helper function to exercise annotation path."""
            sprite.render(surface)

        sprite = SpriteInterface()
        mock_surface = Mock(spec=pygame.Surface)
        test_render_function(sprite, mock_surface)
        assert test_render_function is not None


class TestInterfacesTypeCheckingReload:
    """Force TYPE_CHECKING path by reloading with guard set."""

    def test_reload_with_type_checking_true(self):
        """Temporarily set TYPE_CHECKING to True and reload module."""
        original = typing.TYPE_CHECKING
        try:
            typing.TYPE_CHECKING = True
            reloaded = reload(interfaces_module)
            assert hasattr(reloaded, "SpriteInterface")
            assert hasattr(reloaded, "SceneInterface")
        finally:
            typing.TYPE_CHECKING = original
