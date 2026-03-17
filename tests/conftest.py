"""Shared test fixtures for the GlitchyGames test suite.

This module provides common fixtures and utilities used across multiple test files.
Uses pytest-mock's mocker fixture for automatic patch cleanup where possible.
"""

import os
import sys
from pathlib import Path

import pytest

# Use dummy SDL video driver in CI to prevent segfaults in headless environments.
# This must be set before pygame is imported/initialized in any test worker.
if os.environ.get('CI') == 'true' and 'SDL_VIDEODRIVER' not in os.environ:
    os.environ['SDL_VIDEODRIVER'] = 'dummy'

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.events import ResourceManager
from glitchygames.fonts import FontManager
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sprites import (
    FocusableSingletonBitmappySprite,
    Singleton,
    SingletonBitmappySprite,
)
from tests.mocks import MockFactory


def pytest_configure(config):
    """Configure pytest to enable strict event handling for all tests."""
    # This ensures that unhandled events cause tests to fail, catching bugs
    # The no_unhandled_events flag is enabled globally in mock_game fixture


@pytest.fixture(autouse=True)
def setup_conditional_pygame_mocks(request, mocker):
    """Set up pygame mocks conditionally based on test file.

    Uses pytest-mock's mocker fixture for automatic cleanup — no manual
    teardown needed.

    Yields:
        dict: The mock pygame patches dictionary, or an empty dict if no mocks are needed.

    """
    # Check if this is a scene test or game objects test that needs mocks
    test_file = str(request.node.fspath)
    needs_mocks = 'scene' in test_file.lower() or 'game_objects' in test_file.lower()

    if needs_mocks:
        # Ensure pygame is properly initialized for mocks
        import pygame

        if not pygame.get_init():
            pygame.init()
        # Ensure display mode is set (needed after pygame.quit() from other tests)
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((800, 600))

        # Use mocker-based mocks — cleanup is automatic
        yield MockFactory.setup_pygame_mocks_with_mocker(mocker)
    else:
        # No mocks needed for this test
        yield {}


def _reset_all_singleton_instances():
    """Reset all singleton class instances to prevent test contamination.

    Singleton instances (SceneManager, MenuBar, etc.) persist across tests
    and can carry stale state from mocked pygame environments into tests
    that need real pygame. This resets both parent and subclass __instance__
    attributes since Python sets cls.__instance__ on the subclass, not the parent.
    """
    SceneManager._reset()

    # Reset ResourceManager singleton instances (FontManager, event managers, etc.)
    ResourceManager.__instances__.clear()

    # Reset FontManager class-level caches that may hold mock objects
    FontManager._font_cache.clear()
    FontManager.OPTIONS.clear()

    # Reset all singleton base classes and their subclasses
    for singleton_base in (Singleton, SingletonBitmappySprite, FocusableSingletonBitmappySprite):
        singleton_base.__instance__ = None
        for subclass in singleton_base.__subclasses__():
            if hasattr(subclass, '__instance__'):
                subclass.__instance__ = None


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before each test to prevent contamination."""
    _reset_all_singleton_instances()
    yield
    _reset_all_singleton_instances()


@pytest.fixture
def mock_game_args(mocker):
    """Create mock command line arguments for testing.

    Returns:
        object: The result.

    """
    mock_args = mocker.Mock()
    mock_args.fps = 60
    mock_args.resolution = '800x600'  # String format expected by GameEngine
    mock_args.windowed = True
    mock_args.use_gfxdraw = False
    mock_args.update_type = 'update'
    mock_args.fps_refresh_rate = 1
    mock_args.profile = False
    mock_args.test_flag = False
    mock_args.unknown_args = []
    mock_args.log_level = 'INFO'  # Add missing log_level attribute
    return mock_args


@pytest.fixture
def mock_pygame_patches(mocker):
    """Set up pygame mocks for testing.

    Uses pytest-mock's mocker fixture for automatic cleanup — no manual
    teardown needed.

    Returns:
        object: The result.

    """
    # Ensure pygame is properly initialized for mocks
    import pygame

    if not pygame.get_init():
        pygame.init()
    # Ensure display mode is set (needed after pygame.quit() from other tests)
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((800, 600))

    return MockFactory.setup_pygame_mocks_with_mocker(mocker)


@pytest.fixture
def mock_game(mocker):
    """Create a mock game scene for testing.

    Returns:
        object: The result.

    """

    class MockGame(Scene):
        """Simple mock game scene for testing."""

        NAME = 'MockGame'
        VERSION = '1.0'

        def __init__(self, options=None, groups=None):
            if options is None:
                options = {
                    'debug_events': False,
                    # Enable globally to catch unhandled events as bugs
                    'no_unhandled_events': True,
                }
            if groups is None:
                groups = mocker.Mock()  # Mock pygame.sprite.Group
            super().__init__(options=options, groups=groups)
            self.fps = 60
            self.background_color = (0, 0, 0)
            self.next_scene = self

        @classmethod
        def args(cls, parser):
            """Add mock game arguments.

            Returns:
                object: The result.

            """
            parser.add_argument('--test-flag', action='store_true', help='Test flag')
            return parser

        def update(self):
            """Mock update method."""

    return MockGame


@pytest.fixture
def mock_game_with_args(mock_game):
    """Create a mock game that properly handles command line arguments.

    Returns:
        object: The result.

    """

    class MockGameWithArgs(mock_game):
        """Mock game that properly handles command line arguments."""

        @classmethod
        def args(cls, parser):
            """Add mock game arguments.

            Returns:
                object: The result.

            """
            parser.add_argument('--test-flag', action='store_true', help='Test flag')
            return parser

    return MockGameWithArgs


@pytest.fixture
def mock_surface():
    """Create a mock pygame surface for testing.

    Returns:
        object: The result.

    """
    return MockFactory.create_pygame_surface_mock(32, 32)


@pytest.fixture
def mock_joystick_manager():
    """Create a mock joystick manager for testing.

    Returns:
        object: The result.

    """
    return MockFactory.create_joystick_manager_mock(joystick_count=0)  # No joysticks by default


@pytest.fixture
def mock_managers(mocker):
    """Create mock managers for testing.

    Returns:
        object: The result.

    """
    return {
        'joystick_manager': mocker.Mock(),
        'font_manager': mocker.Mock(),
        'game_manager': mocker.Mock(),
        'keyboard_manager': mocker.Mock(),
        'midi_manager': mocker.Mock(),
        'mouse_manager': mocker.Mock(),
        'window_manager': mocker.Mock(),
        'audio_manager': mocker.Mock(),
        'controller_manager': mocker.Mock(),
        'drop_manager': mocker.Mock(),
        'touch_manager': mocker.Mock(),
    }
