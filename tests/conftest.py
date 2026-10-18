"""Shared test fixtures for the GlitchyGames test suite.

This module provides common fixtures and utilities used across multiple test files.
Uses pytest-mock's mocker fixture for automatic patch cleanup where possible.
"""

import contextlib
import logging
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

# Imported after the SDL environment is set up above
import pygame

from glitchygames.engine import GameEngine
from glitchygames.events import ResourceManager
from glitchygames.fonts import FontManager
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sprites import (
    FocusableSingletonBitmappySprite,
    Singleton,
    SingletonBitmappySprite,
)
from tests.mocks import MockFactory


def _load_lazy_pygame_modules() -> None:
    """Run the imports pygame defers until first use, while pygame is still unpatched.

    pygame imports `sndarray` and `surfarray` lazily: the module body runs on the first
    attribute access. `sndarray` does `from pygame import mixer` there, so if that first access
    happens inside a test that patched `pygame.mixer` (MockFactory's pygame patches do), the
    mock is bound into `pygame.sndarray` for the rest of the process and every later
    `pygame.sndarray.make_sound` returns a Mock. Loading them here binds the real modules.
    """
    for lazy_module, attribute_name in (
        (pygame.sndarray, 'make_sound'),
        (pygame.surfarray, 'pixels3d'),
    ):
        getattr(lazy_module, attribute_name)


_load_lazy_pygame_modules()

# Real logging entry points, captured at import time before any test can patch them.
_REAL_LOGGING_GET_LOGGER = logging.getLogger
_REAL_LOGGER_MANAGER = logging.Logger.manager


def _restore_patched_logging_globals() -> list[str]:
    """Restore any process-wide logging globals a test replaced, and name them.

    Returns:
        list[str]: Descriptions of each global that had been replaced.

    """
    replaced_globals = []
    if logging.getLogger is not _REAL_LOGGING_GET_LOGGER:
        replaced_globals.append(f'logging.getLogger (replaced with {logging.getLogger!r})')
        logging.getLogger = _REAL_LOGGING_GET_LOGGER
    if logging.Logger.manager is not _REAL_LOGGER_MANAGER:
        replaced_globals.append(
            f'logging.Logger.manager (replaced with {logging.Logger.manager!r})',
        )
        logging.Logger.manager = _REAL_LOGGER_MANAGER
    return replaced_globals


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """Fail any test that replaces process-wide logging globals.

    Patching e.g. 'some.module.logging.getLogger' replaces logging.getLogger for the
    whole process, not just that module. pytest's own logging plugin calls
    logging.getLogger() at the start of teardown, before mocker undoes the patch, and
    crashes on the mock; the patch is then never undone and every later test errors.

    This check runs at the end of the test call, before teardown, so the offending test
    fails with an explanation. The real globals are restored first so the failure
    cannot cascade into other tests.

    Returns:
        object: The wrapped hook's result.

    """
    result = yield
    replaced_globals = _restore_patched_logging_globals()
    if replaced_globals:
        pytest.fail(
            f'{item.nodeid} replaced process-wide logging globals: '
            f'{"; ".join(replaced_globals)}. Inject a mock logger instead (e.g. a '
            "constructor 'logger' argument) or patch the module's own logger object.",
            pytrace=False,
        )
    return result


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
def restore_gil_switch_interval():
    """Restore the GIL switch interval after each test.

    GameEngine.__init__ calls sys.setswitchinterval(); tests that construct a real GameEngine
    would otherwise leave the whole process at 0.5 ms.
    """
    previous_interval = sys.getswitchinterval()
    yield
    sys.setswitchinterval(previous_interval)


@pytest.fixture(autouse=True)
def restore_game_engine_class_state(mocker):
    """Restore the GameEngine class attributes that engine code writes, after each test.

    GameEngine.__init__ stores its game in the class attribute `game` and its parsed options
    in `OPTIONS`, and GameEngine.initialize_icon stores the icon in `icon`. A test that runs
    them with mocks (a Mock game, a mocked pygame.image.load) would otherwise leave the mocks
    there for every later test on the worker: a real GameEngine then fails in
    initialize_system_icons with "Argument to set_icon must be a Surface".
    """
    for attribute_name in ('game', 'icon', 'OPTIONS'):
        # Patched with its own value: whatever the test assigns is undone at teardown
        mocker.patch.object(GameEngine, attribute_name, getattr(GameEngine, attribute_name))


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
def mock_game_with_args(mock_game: type[Scene]):
    """Create a mock game that properly handles command line arguments.

    Returns:
        type[Scene]: A Scene subclass with args support.

    """

    class MockGameWithArgs(mock_game):  # ty: ignore[unsupported-base]
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


@pytest.fixture(autouse=True)
def ensure_pygame_graceful_quit():
    """Ensure pygame is properly initialized before tests and gracefully quit after.

    This fixture handles the common case where a previous test may have called
    pygame.quit(), leaving the subsystem in an uninitialized state. It ensures
    pygame is initialized before each test and gracefully shuts it down afterward,
    preventing segfaults and resource leaks across test boundaries.
    """
    import pygame

    # Ensure pygame is initialized before the test runs
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        with contextlib.suppress(pygame.error):
            pygame.display.set_mode((800, 600))

    yield

    # Graceful cleanup: quit pygame subsystems that may hold resources,
    # then reinitialize so the next test starts with a clean state.
    try:
        if pygame.get_init():
            pygame.quit()
    except pygame.error:
        pass  # Already quit or never initialized

    # Reinitialize for the next test
    try:
        pygame.init()
        pygame.display.set_mode((800, 600))
    except pygame.error:
        pass  # Headless environment
