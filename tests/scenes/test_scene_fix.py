#!/usr/bin/env python3
"""Quick test to verify the Scene fix works."""

import pytest
from tests.mocks.test_mock_factory import MockFactory


class TestSceneFix:
    """Test that Scene can access SceneManager methods."""

    def setup_method(self):
        """Set up test fixtures using centralized mocks."""
        # Use centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def teardown_method(self):
        """Clean up after tests."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_scene_has_collision_methods(self):
        """Test that Scene has collision detection and sprite management methods."""
        from glitchygames.scenes import Scene, SceneManager
        
        # Test that Scene has the methods directly
        scene = Scene()
        scene_manager = SceneManager()
        scene.scene_manager = scene_manager
        
        # Test that the methods exist on the Scene object
        assert hasattr(scene, '_get_collided_sprites')
        assert hasattr(scene, '_get_focusable_sprites')
        assert hasattr(scene, '_get_focused_sprites')
        assert hasattr(scene, '_has_focusable_sprites')
        
        # Test that Scene can call these methods directly
        # This should not raise an AttributeError
        result = scene._get_collided_sprites((100, 100))
        assert result is not None  # Should return some result (even if empty list)
        
        # Test that Scene can access SceneManager through scene_manager property
        assert scene.scene_manager is not None
        assert hasattr(scene.scene_manager, 'all_sprites')
