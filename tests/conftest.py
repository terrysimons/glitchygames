"""Shared test fixtures for the GlitchyGames test suite.

This module provides common fixtures and utilities used across multiple test files.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from mocks.test_mock_factory import MockFactory


@pytest.fixture
def mock_game_args():
    """Create mock command line arguments for testing."""
    mock_args = Mock()
    mock_args.fps = 60
    mock_args.resolution = "800x600"  # String format expected by GameEngine
    mock_args.windowed = True
    mock_args.use_gfxdraw = False
    mock_args.update_type = "timestep"
    mock_args.fps_refresh_rate = 1
    mock_args.profile = False
    mock_args.test_flag = False
    mock_args.unknown_args = []
    mock_args.log_level = "INFO"  # Add missing log_level attribute
    return mock_args


@pytest.fixture
def mock_pygame_patches():
    """Set up pygame mocks for testing."""
    patchers = MockFactory.setup_pygame_mocks()
    for patcher in patchers:
        patcher.start()
    
    yield patchers
    
    MockFactory.teardown_pygame_mocks(patchers)


@pytest.fixture
def mock_game():
    """Create a mock game scene for testing."""
    from glitchygames.scenes import Scene
    
    class MockGame(Scene):
        """Simple mock game scene for testing."""
        
        NAME = "MockGame"
        VERSION = "1.0"

        def __init__(self, options=None, groups=None):
            if options is None:
                options = {
                    "debug_events": False,
                    "no_unhandled_events": False
                }
            if groups is None:
                groups = Mock()  # Mock pygame.sprite.Group
            super().__init__(options=options, groups=groups)
            self.fps = 60
            self.background_color = (0, 0, 0)
            self.next_scene = self
        
        @classmethod
        def args(cls, parser):
            """Add mock game arguments."""
            parser.add_argument("--test-flag", action="store_true", help="Test flag")
            return parser
        
        def update(self):
            """Mock update method."""
            pass

    return MockGame


@pytest.fixture
def mock_game_with_args(mock_game):
    """Create a mock game that properly handles command line arguments."""
    
    class MockGameWithArgs(mock_game):
        """Mock game that properly handles command line arguments."""
        
        @classmethod
        def args(cls, parser):
            """Add mock game arguments."""
            parser.add_argument("--test-flag", action="store_true", help="Test flag")
            return parser

    return MockGameWithArgs


@pytest.fixture
def mock_surface():
    """Create a mock pygame surface for testing."""
    return MockFactory.create_pygame_surface_mock(32, 32)


@pytest.fixture
def mock_joystick_manager():
    """Create a mock joystick manager for testing."""
    from tests.mocks.test_mock_factory import MockFactory
    return MockFactory.create_joystick_manager_mock(joystick_count=0)  # No joysticks by default


@pytest.fixture
def mock_managers():
    """Create mock managers for testing."""
    return {
        'joystick_manager': Mock(),
        'font_manager': Mock(),
        'game_manager': Mock(),
        'keyboard_manager': Mock(),
        'midi_manager': Mock(),
        'mouse_manager': Mock(),
        'window_manager': Mock(),
        'audio_manager': Mock(),
        'controller_manager': Mock(),
        'drop_manager': Mock(),
        'touch_manager': Mock(),
    }
