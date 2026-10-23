"""Shared test fixtures for the GlitchyGames test suite.

This module provides common fixtures and utilities used across multiple test files.
Uses pytest-mock's mocker fixture for automatic patch cleanup where possible.
"""

import contextlib
import logging
import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

# Importing tests.sdl_defaults defaults the SDL drivers to dummy (keeping any value the invoker
# set); it must come before pygame is imported/initialized in any test worker
from tests.sdl_defaults import SDL_VARIABLES_DEFAULTED_AT_STARTUP  # isort: skip

import pygame

from glitchygames import pixel_snap, randomness, sources
from glitchygames.backgrounds import set_active_default_background_pattern
from glitchygames.engine import GameEngine
from glitchygames.events import ResourceManager
from glitchygames.fonts import FontManager
from glitchygames.input.state import reset_current_input
from glitchygames.recording import reset_internal_post_tracking
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sprites import (
    FocusableSingletonBitmappySprite,
    Singleton,
    SingletonBitmappySprite,
)
from tests.display_canvas import (
    CANVAS_PATTERN,
    TEST_DISPLAY_SIZE,
    display_looks_entirely_black,
    present_display,
    real_display_surface,
    show_canvas,
    show_canvas_on_new_display,
)
from tests.sdl_defaults import SDL_DRIVER_ENVIRONMENT_FOR_RUN
from tests.sdl_driver_isolation import (
    SdlDriverState,
    live_sdl_driver_state,
    restore_run_sdl_drivers,
)
from tests.signal_handlers import preserved_signal_handlers


def _load_lazy_pygame_modules() -> None:
    """Run the imports pygame defers until first use, while pygame is still unpatched.

    pygame imports `sndarray` and `surfarray` lazily: the module body runs on the first
    attribute access. `sndarray` does `from pygame import mixer` there, so if that first access
    happens inside a test that patched `pygame.mixer` (e.g. `mocker.patch('pygame.mixer', ...)`),
    the mock is bound into `pygame.sndarray` for the rest of the process and every later
    `pygame.sndarray.make_sound` returns a Mock. Loading them here binds the real modules
    (tests/world/test_mock_isolation.py checks this).
    """
    for lazy_module, attribute_name in (
        (pygame.sndarray, 'make_sound'),
        (pygame.surfarray, 'pixels3d'),
    ):
        getattr(lazy_module, attribute_name)


_load_lazy_pygame_modules()

# The test display rule (tests/display_canvas.py): every test starts on the canvas pattern, and
# a test whose last frame is entirely black fails as a rendering bug
BLACK_FRAME_EXPECTED_MARKER = 'black_frame_expected'


@pytest.fixture(scope='session')
def sdl_variables_defaulted_at_startup() -> tuple[str, ...]:
    """Names of the SDL driver variables this run defaulted to 'dummy' (the others were preset).

    Returns:
        tuple[str, ...]: The variables that were not set when the test process started.

    """
    return SDL_VARIABLES_DEFAULTED_AT_STARTUP


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
    """Run the test on the canvas, show what it drew, and fail it on a logging or black-frame bug.

    The test display rule (tests/display_canvas.py): a fixture that set a new display mode
    (a fresh, black display) and drew nothing gets the canvas again before the test body, and
    after the body the display is presented and a last frame that looks entirely black fails
    the test (_fail_on_entirely_black_frame).

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
    display_surface = real_display_surface()
    if display_surface is not None and display_looks_entirely_black(display_surface):
        show_canvas()
    try:
        result = yield
    finally:
        # Show what the test drew (a test that only draws, never presents, is visible too)
        if real_display_surface() is not None:
            present_display()
    replaced_globals = _restore_patched_logging_globals()
    if replaced_globals:
        pytest.fail(
            f'{item.nodeid} replaced process-wide logging globals: '
            f'{"; ".join(replaced_globals)}. Inject a mock logger instead (e.g. a '
            "constructor 'logger' argument) or patch the module's own logger object.",
            pytrace=False,
        )
    _fail_on_entirely_black_frame(item=item)
    return result


def _fail_on_entirely_black_frame(
    *, item: pytest.Item, display_surface: pygame.Surface | None = None
) -> None:
    """Fail a test whose last frame looks entirely black: a rendering bug (the display rule).

    Every test starts on the canvas pattern (ensure_pygame_graceful_quit), so a black display at
    the end of the test body was drawn, or set up, by the test. This runs in pytest_runtest_call,
    before fixture teardown, so no teardown step can leave a black frame behind to trip it.
    It judges what the window shows (display_looks_entirely_black): on a display with per-pixel
    alpha (cocoa's) alpha 0 shows black whatever the colour. A test whose last frame is black by
    definition opts out with @pytest.mark.black_frame_expected(reason=...).

    Args:
        item: The test that just ran.
        display_surface: The frame judged; None for the real display (tests of the guard pass
            a surface with per-pixel alpha, which the dummy display does not have).

    """
    if item.get_closest_marker(BLACK_FRAME_EXPECTED_MARKER) is not None:
        return
    if display_surface is None:
        display_surface = real_display_surface()
    if display_surface is None or not display_looks_entirely_black(display_surface):
        return
    pytest.fail(
        f"rendering bug: the test's last frame looks entirely black ({item.nodeid}). Tests "
        'start on the canvas pattern and scenes that set no background show it (tests/'
        'display_canvas.py); something in this test drew black (or, on a display with '
        'per-pixel alpha, alpha 0) over everything.',
        pytrace=False,
    )


def pytest_configure(config):
    """Configure pytest to enable strict event handling for all tests, and register markers."""
    # This ensures that unhandled events cause tests to fail, catching bugs
    # The no_unhandled_events flag is enabled globally in mock_game fixture
    config.addinivalue_line(
        'markers',
        f"{BLACK_FRAME_EXPECTED_MARKER}(reason): the test's last frame looks entirely black by "
        'definition (e.g. a fade to black), so the black-frame guard skips it',
    )


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
def restore_signal_handlers():
    """Put back the process's signal handlers after each test (tests/signal_handlers.py).

    A test that runs GameEngine.start with _shutdown mocked would otherwise leave the engine's
    exit_on_signal installed for the rest of the worker's tests.
    """
    with preserved_signal_handlers():
        yield


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
    initialize_system_icons with "Argument to set_icon must be a Surface". GameEngine.__init__
    also sets `USE_FASTEVENTS` on a (mocked) old pygame, which would make every later engine on
    the worker create fastevent live sources (BUGS.md #65).
    """
    for attribute_name in ('game', 'icon', 'OPTIONS', 'USE_FASTEVENTS'):
        # Patched with its own value: whatever the test assigns is undone at teardown
        mocker.patch.object(GameEngine, attribute_name, getattr(GameEngine, attribute_name))


@pytest.fixture(autouse=True)
def fresh_random_streams(mocker):
    """Give each test an unseeded set of engine random streams (glitchygames/randomness.py).

    GameEngine and reset_streams() set the process-wide master seed and cache streams; without
    this, one test's seed and half-used streams would carry into the next test on the worker.
    """
    mocker.patch.object(randomness, '_STATE', randomness.EngineRandomState())


@pytest.fixture(autouse=True)
def reset_engine_sources():
    """Give every test fresh live doors and reset them afterwards (glitchygames/sources.py).

    reset_sources() tells the installed sources (on_uninstalled), which is where a replay stops
    tracking code-posted events (Task 12), so no tracking leaks into the next test. The frame's
    polled input (glitchygames/input/state.py) is reset too: reset_sources() leaves it alone.
    So is the internal-post tracker (glitchygames/recording.py: no owners, nothing pending),
    so a recorder a test left open cannot keep tracking into the next test.
    """
    sources.reset_sources()
    reset_current_input()
    reset_internal_post_tracking()
    yield
    sources.reset_sources()
    reset_current_input()
    reset_internal_post_tracking()


@pytest.fixture(autouse=True)
def reset_default_snap_mode():
    """Start and end each test with the engine default snap mode (NEAREST_HALF_UP).

    The active default is process-global (glitchygames/pixel_snap.py) and scene setup sets it
    from Scene.PIXEL_SNAP_MODE; without this, one test's scene would change snapping for the
    next test on the worker.
    """
    pixel_snap.set_active_default_snap_mode(pixel_snap.PixelSnapMode.NEAREST_HALF_UP)
    yield
    pixel_snap.set_active_default_snap_mode(pixel_snap.PixelSnapMode.NEAREST_HALF_UP)


@pytest.fixture(autouse=True)
def reset_default_background_pattern():
    """Start and end each test with the canvas pattern as the default scene background.

    The default is process-global (glitchygames/backgrounds.py) and GameEngine sets it from
    --default-background; without this, one test's engine would change the next test's scenes.
    """
    set_active_default_background_pattern(pattern=CANVAS_PATTERN)
    yield
    set_active_default_background_pattern(pattern=CANVAS_PATTERN)


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


def _start_pygame_and_the_test_display() -> None:
    """Start pygame and open the test display, unless they are already running."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        with contextlib.suppress(pygame.error):
            pygame.display.set_mode(TEST_DISPLAY_SIZE)


@pytest.fixture(scope='session')
def run_sdl_driver_state() -> SdlDriverState:
    """The drivers this run's display and mixer run on, read before any test body ran.

    Set up in the first test's setup (ensure_pygame_graceful_quit asks for it), while the SDL
    driver variables are still the run's (tests/sdl_defaults.py): every later test is put back
    on these drivers (tests/sdl_driver_isolation.py).

    Returns:
        SdlDriverState: The run's live video and audio drivers and the mixer's format.

    """
    _start_pygame_and_the_test_display()
    return live_sdl_driver_state()


@pytest.fixture(autouse=True)
def ensure_pygame_graceful_quit(run_sdl_driver_state: SdlDriverState):
    """Give every test an initialized pygame showing the canvas pattern; isolate its sound.

    pygame stays initialized for the whole run: quitting and re-initializing it after every
    test cost about 30 ms per test (most of a serial run). Before each test, pygame and the
    800x600 display are started again if a test quit them, and the canvas is drawn and presented
    (the test display rule, tests/display_canvas.py). After each test, every mixer
    channel is stopped, so no sound plays on into the next test (audibly, on a real audio
    driver), and a display a test resized is set back to the default size, showing the canvas.
    The SDL driver variables, display and mixer a test moved off the run's drivers (an engine
    run with --headless moves them to 'dummy') are put back on them, showing the canvas
    (tests/sdl_driver_isolation.py); a test that changed none of them costs a few reads.

    Args:
        run_sdl_driver_state: The drivers the run's display and mixer run on.

    """
    # Ensure pygame is initialized before the test runs
    _start_pygame_and_the_test_display()
    # The canvas: a test that draws nothing shows the pattern, and no test sees an earlier
    # test's drawing (the guard in pytest_runtest_call fails a test that ends on all black)
    show_canvas()

    yield

    if pygame.mixer.get_init() is not None:
        pygame.mixer.stop()
    restore_run_sdl_drivers(
        run_environment=SDL_DRIVER_ENVIRONMENT_FOR_RUN, run_state=run_sdl_driver_state
    )
    with contextlib.suppress(pygame.error):
        surface = pygame.display.get_surface() if pygame.get_init() else None
        if surface is not None and surface.get_size() != TEST_DISPLAY_SIZE:
            # Shown at once: a window set_mode resizes is black until presented, and on a real
            # driver it would stay black (under the last scene's caption) while the worker waits
            # for its next test, or for the run to end
            show_canvas_on_new_display(size=TEST_DISPLAY_SIZE)
