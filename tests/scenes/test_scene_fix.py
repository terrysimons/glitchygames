#!/usr/bin/env python3
"""Quick test to verify the Scene fix works."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent))

# Mock pygame before importing
with patch("pygame.init"), \
     patch("pygame.display.init"), \
     patch("pygame.display.set_mode") as mock_set_mode, \
     patch("pygame.display.get_surface") as mock_get_surface:
    
    # Configure mocks
    mock_surface = Mock()
    mock_surface.get_width.return_value = 800
    mock_surface.get_height.return_value = 600
    mock_surface.get_size.return_value = (800, 600)
    mock_set_mode.return_value = mock_surface
    mock_get_surface.return_value = mock_surface
    
    from glitchygames.scenes import Scene, SceneManager
    
    # Test that Scene can access SceneManager methods
    scene_manager = SceneManager()
    scene = Scene()
    scene.scene_manager = scene_manager
    
    # Test that the methods exist
    print('_get_collided_sprites exists:', hasattr(scene_manager, '_get_collided_sprites'))
    print('_get_focusable_sprites exists:', hasattr(scene_manager, '_get_focusable_sprites'))
    print('_get_focused_sprites exists:', hasattr(scene_manager, '_get_focused_sprites'))
    print('_has_focusable_sprites exists:', hasattr(scene_manager, '_has_focusable_sprites'))
    print('_unfocus_sprites exists:', hasattr(scene_manager, '_unfocus_sprites'))
    
    # Test that Scene can call these methods through scene_manager
    try:
        # This should not raise an AttributeError
        result = scene.scene_manager._get_collided_sprites((100, 100))
        print('Scene can call _get_collided_sprites through scene_manager')
    except Exception as e:
        print(f'Error calling _get_collided_sprites: {e}')
    
    print('Scene fix verification complete!')
