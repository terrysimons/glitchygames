"""Test coverage for SceneInterface."""

import inspect
from unittest.mock import Mock

from glitchygames.interfaces import SceneInterface

# Suppress PLR6301 for test methods (they need self for fixtures)
# ruff: noqa: PLR6301


class TestSceneInterface:
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

    def test_scene_interface_inheritance(self):
        """Test that SceneInterface can be inherited."""
        class TestScene(SceneInterface):
            def switch_to_scene(self, next_scene):
                pass

            def terminate(self):
                pass

            def play(self):
                pass

            def pause(self):
                pass

        scene = TestScene()
        assert isinstance(scene, SceneInterface)
        assert isinstance(scene, TestScene)

    def test_scene_interface_method_signatures(self):
        """Test that SceneInterface methods have correct signatures."""
        # Check switch_to_scene signature
        switch_sig = inspect.signature(SceneInterface.switch_to_scene)
        assert len(switch_sig.parameters) == 2  # self, next_scene
        assert 'next_scene' in switch_sig.parameters

        # Check terminate signature
        terminate_sig = inspect.signature(SceneInterface.terminate)
        assert len(terminate_sig.parameters) == 1  # self

        # Check play signature
        play_sig = inspect.signature(SceneInterface.play)
        assert len(play_sig.parameters) == 1  # self

        # Check pause signature
        pause_sig = inspect.signature(SceneInterface.pause)
        assert len(pause_sig.parameters) == 1  # self

    def test_scene_interface_method_return_types(self):
        """Test that SceneInterface methods have correct return type annotations."""
        # Check switch_to_scene return type
        switch_annotations = SceneInterface.switch_to_scene.__annotations__
        assert 'return' in switch_annotations
        assert switch_annotations['return'] == 'None'

        # Check terminate return type
        terminate_annotations = SceneInterface.terminate.__annotations__
        assert 'return' in terminate_annotations
        assert terminate_annotations['return'] == 'None'

        # Check play return type
        play_annotations = SceneInterface.play.__annotations__
        assert 'return' in play_annotations
        assert play_annotations['return'] == 'None'

        # Check pause return type
        pause_annotations = SceneInterface.pause.__annotations__
        assert 'return' in pause_annotations
        assert pause_annotations['return'] == 'None'

    def test_scene_interface_parameter_types(self):
        """Test that SceneInterface method parameters have correct type annotations."""
        # Check switch_to_scene parameter type
        switch_sig = inspect.signature(SceneInterface.switch_to_scene)
        next_scene_param = switch_sig.parameters['next_scene']
        assert next_scene_param.annotation == 'SceneInterface'
