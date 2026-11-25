"""The shared test harness, loaded by the root conftest.py for every package's tests.

This module provides common fixtures and utilities used across multiple test files.
Uses pytest-mock's mocker fixture for automatic patch cleanup where possible.
"""

import contextlib
import functools
import gc
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from hypothesis import settings

# No test reaches the real AI service, which would load gigabytes of models on a machine that
# has it, and only there: every client gets "not installed" unless a test names an install. Set,
# not defaulted, and the program and user root variables removed, as each wins over this one in
# glitchygames/ai_link.py's service_locations. So nothing a developer's shell exports reaches the
# suite, as tests/test_ai_service_isolation_guard.py checks
os.environ['GLITCHYGAMES_AI_INSTALL_ROOT'] = '/nonexistent/glitchygames-ai-service'
os.environ.pop('GLITCHYGAMES_AI_PROGRAM_ROOT', None)
os.environ.pop('GLITCHYGAMES_AI_USER_ROOT', None)

# No test writes to the user's sound cache folder: an empty root turns cache disk's disk layer off
# (glitchygames/audio/disk_cache.py, rule 6), so disk runs as ram. Set, not defaulted, so a value
# exported in a developer's shell never reaches the suite. A test of the disk layer asks for the
# disk_sound_cache fixture (tests/disk_sound_cache.py), which points it at the test's own folder
os.environ['GLITCHYGAMES_SOUND_CACHE_ROOT'] = ''

# Importing tests.sdl_defaults defaults the SDL drivers to dummy (keeping any value the invoker
# set); it must come before pygame is imported/initialized in any test worker
from tests.sdl_defaults import SDL_VARIABLES_DEFAULTED_AT_STARTUP  # isort: skip

import pygame

from glitchygames import engine_context, pixel_snap, process, randomness, sources
from glitchygames.audio.engine import AUDIO_ENGINE_SLOT
from glitchygames.audio.instruments import registry as instruments_registry
from glitchygames.audio.library import ENGINE_SOUND_CACHE
from glitchygames.audio.live import (
    live_streams_holding_chunks,
    take_unreleased_live_stream_reports,
)
from glitchygames.audio.voices import release_channels
from glitchygames.backgrounds import (
    DEFAULT_BACKGROUND_PATTERN,
    set_active_default_background_pattern,
)
from glitchygames.clipboard import InProcessClipboard, install_clipboard
from glitchygames.engine import GameEngine
from glitchygames.engine.game_engine import (
    CURRENT_ENGINE_SLOT,
    report_fatal_signals_with_faulthandler,
)
from glitchygames.engine_context import current_context, default_context
from glitchygames.events.base import SHARED_INSTANCES_SLOT, UNHANDLED_EVENT_TYPES_SLOT
from glitchygames.feature_flags import FLAG_OPTIONS_SLOT
from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import FONT_OPTIONS_SLOT
from glitchygames.input.state import reset_current_input
from glitchygames.performance.adaptive_clamping import PERFORMANCE_MANAGERS_SLOT
from glitchygames.recording import reset_internal_post_tracking
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sprites.bitmappy_sprite import SINGLETONS_SLOT
from glitchygames.sprites.compiled_sprites import ENGINE_SPRITE_CACHE
from glitchygames.sprites.sprite import SPRITE_COUNTERS_SLOT
from glitchygames.user_files import install_user_files
from tests.ai_service_stand_in import CONTROL_SCRIPT_NAME, python_twin
from tests.child_process_guard import ChildProcessGuard, controller_sweep_lines
from tests.display_canvas import (
    CANVAS_PATTERN,
    TEST_DISPLAY_SIZE,
    canvas_shown_bytes,
    display_looks_entirely_black,
    present_display,
    real_display_surface,
    show_canvas,
    show_canvas_on_new_display,
)
from tests.engine_source import ENGINE_DIRECTORY
from tests.engine_written_state import engine_written_state_for_run, reset_engine_written_state
from tests.faulthandler_guard import faulthandler_left_on
from tests.garbage_collection import (
    process_memory_release,
    release_raised_parameters,
    release_test_instance,
)
from tests.git_environment import clear_git_repository_variables
from tests.hidden_test_windows import hide_test_windows
from tests.leaked_state_guard import (
    drop_patches_to_put_back,
    leak_message,
    watch_process_state,
)
from tests.sdl_defaults import SDL_DRIVER_ENVIRONMENT_FOR_RUN
from tests.sdl_driver_isolation import (
    SdlDriverState,
    live_sdl_driver_state,
    restore_run_sdl_drivers,
)
from tests.signal_handlers import preserved_signal_handlers

if TYPE_CHECKING:
    from collections.abc import Generator

    from tests.leaked_state_guard import LeakCheck

# A crash on a thread without the GIL (SDL's audio thread on the native driver) fails its test
# with a traceback instead of hanging the worker forever in pygame's parachute (installed by the
# import above): pytest enables its faulthandler after this module loads, and that then changes
# only where the traceback is written (tests/engine/test_engine_fatal_signals.py)
report_fatal_signals_with_faulthandler()

# The repository and its own engine source (src/glitchygames): what a test means by "the
# checkout", whichever copy of the engine is imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECKOUT_ENGINE_DIRECTORY = PROJECT_ROOT / ENGINE_DIRECTORY
# Windows can't run the stand-in AI control script (a POSIX shell script): there,
# stand_in_ai_control_scripts runs its Python twin
CONTROL_SCRIPTS_RUN_THROUGH_THEIR_TWINS = sys.platform == 'win32'


# Before any window opens: a real driver's test windows are hidden, so the machine's pointer and
# keyboard never reach a test (tests/hidden_test_windows.py, BUGS.md #225)
TEST_WINDOWS_HIDDEN = hide_test_windows()
# Before any test, worker or native run: git finds repositories where tests point it, not the one a
# git hook (pre-push) was started for (tests/git_environment.py)
GIT_VARIABLES_CLEARED_AT_STARTUP = clear_git_repository_variables()


def imported_engine_directory() -> Path:
    """Return the imported glitchygames' directory: the copy the code under test loads.

    Returns:
        The engine package's directory (``uv sync``: the checkout's src/glitchygames; nox: the
        session's site-packages copy).

    """
    import glitchygames

    return Path(glitchygames.__file__).resolve().parent


def imported_engine_is_the_checkouts() -> bool:
    """Whether the imported glitchygames is this checkout's src/glitchygames.

    True under ``uv sync`` (an editable install, its .pth naming src/), False under nox (a built,
    non-editable copy in the session's site-packages, which names its commit by build stamp).

    Returns:
        Whether the engine imported is the checkout's own source.

    """
    return imported_engine_directory() == CHECKOUT_ENGINE_DIRECTORY


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
# A test that times real work against a tolerance: the test session runs these alone, in one
# process, after the parallel run (noxfile.WALL_CLOCK_MARKER; the owner, 2026-11-23)
WALL_CLOCK_MARKER = 'wall_clock'


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


# Hypothesis without its 200 ms deadline (BUGS.md #157): a speed heuristic, which correct examples
# exceeded on a loaded machine. Settings profiles: see register_profile and load_profile in
# Hypothesis's own settings module (hypothesis/_settings.py, 6.170.9)
settings.register_profile('glitchygames', deadline=None)
settings.load_profile('glitchygames')

# This process's garbage collector and glibc heap trimmer, made as the session starts
_MEMORY_RELEASE = process_memory_release()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """Free the finished test's memory: its class instance's state, its garbage, the free heap.

    Once the test's reports are made and logged, pytest has dropped its fixture values, and
    ``release_test_instance`` empties the test class's instance, which pytest itself keeps for
    the rest of the run, and ``release_raised_parameters`` cuts the traceback of each exception
    parameter it raised, which pytest keeps too; so its scene, sprites and mocks are garbage,
    which the collector frees when memory climbs. On glibc Linux the free heap then goes back to
    the system (``malloc_trim``): tests/garbage_collection.py.

    Returns:
        object: The wrapped hook's result.

    """
    try:
        return (yield)
    finally:
        release_test_instance(item=item)
        release_raised_parameters(item=item)
        _MEMORY_RELEASE.after_test()


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Configure pytest to enable strict event handling for all tests, and register markers.

    On a canvas other than the default (GLITCHYGAMES_TEST_CANVAS), the draws_frames check
    reports without failing: the markers say what each test draws on the default canvas, and a
    test that leaves the default pattern draws on another (glitchygames/testing/
    frame_fingerprints.py). Run first, so the plugin reads the option set here.
    """
    # This ensures that unhandled events cause tests to fail, catching bugs
    # The no_unhandled_events flag is enabled globally in mock_game fixture
    config.addinivalue_line(
        'markers',
        f"{BLACK_FRAME_EXPECTED_MARKER}(reason): the test's last frame looks entirely black by "
        'definition (e.g. a fade to black), so the black-frame guard skips it',
    )
    config.addinivalue_line(
        'markers',
        f'{WALL_CLOCK_MARKER}(reason): the test times real work against a tolerance, which CPU '
        'contention breaks in a parallel run (#287: 4 workers on 4 CPUs left a timer test no '
        'spare core), so nox -s test and test-random run these alone, in one process, after '
        'the rest',
    )
    if CANVAS_PATTERN is not DEFAULT_BACKGROUND_PATTERN:
        config.option.frame_markers_report_only = True


# Optional: a run may load the harness without the frame fingerprints plugin that specifies the
# hook (tests/world/test_mock_isolation.py's inner run), where pytest would refuse it as unknown
@pytest.hookimpl(optionalhook=True)
def pytest_frame_fingerprints_blank_screen(size: tuple[int, int]) -> bytes | None:
    """Tell the draws_frames check what a test that draws nothing leaves: the canvas at its size.

    Every test starts on the canvas (the display rule), so a display still showing it was not
    drawn on (glitchygames/testing/frame_fingerprints.py's draws_frames check).

    Args:
        size: The display's width and height.

    Returns:
        The canvas pattern's shown RGB bytes at that size.

    """
    return canvas_shown_bytes(size=size)


@pytest.hookimpl(trylast=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Kill and list what the run's tests left running when a worker died outright.

    The controller sweeps the run's temporary directory once every worker has ended
    (tests/child_process_guard.py ``controller_sweep_lines``): the backstop for a worker killed
    without unwinding, where neither its tests' cleanup nor ``no_child_process_left_running``
    ran (BUGS.md #275).

    Args:
        terminalreporter: Where the summary is written.
        exitstatus: The run's exit status (unused).
        config: pytest's configuration.

    """
    del exitstatus
    left_running = controller_sweep_lines(config=config)
    if left_running:
        terminalreporter.section('processes left running by this run (now killed)')
        for line in left_running:
            terminalreporter.line(line)


def _reset_all_singleton_instances():
    """Reset every singleton and shared cache so no test sees another test's instances.

    Scene managers live in the engine context (a slot, not a class attribute), so
    SceneManager._reset() clears the current context's managers. The default context's
    ResourceManager instances (a slot too) and FontManager's caches are cleared next, then the
    default context's singleton sprites (BUGS.md #228 items 17, 22).
    """
    SceneManager._reset()
    # The context's audio engine (glitchygames/audio/engine.py) is forgotten, not closed: its
    # channels may be gone with a mixer a test restarted
    current_context().reset_value(slot=AUDIO_ENGINE_SLOT)
    # ...and its channel reservation is handed back and the remembered partition forgotten
    # (ruling R45), so the next engine reserves afresh. SDL_mixer keeps a reservation across a
    # mixer restart while the restarted mixer is back at 8 channels, so an engine's 36 reserved
    # channels, left by a test that never ran the engine's shutdown, made a later test's
    # Sound.play() raise "IndexError: invalid channel index" after another test restarted pygame
    # (tests/test_logging.py). No engine outlives a test here, so nothing needs to keep one
    release_channels()
    # No engine is current until a test makes one (glitchygames.engine.game_engine)
    default_context().reset_value(slot=CURRENT_ENGINE_SLOT)
    # ...and no feature flag has been asked for (glitchygames.feature_flags)
    default_context().reset_value(slot=FLAG_OPTIONS_SLOT)
    # A fresh performance manager each test (glitchygames.performance.adaptive_clamping)
    default_context().reset_value(slot=PERFORMANCE_MANAGERS_SLOT)

    # Reset ResourceManager singleton instances (FontManager, event managers, etc.): the default
    # context's (glitchygames.events.base)
    default_context().reset_value(slot=SHARED_INSTANCES_SLOT)

    # The default context's font options (glitchygames.fonts.font_manager; audit C13)
    default_context().reset_value(slot=FONT_OPTIONS_SLOT)

    # Reset FontManager class-level caches that may hold mock objects
    FontManager._font_cache.clear()
    FontManager.OPTIONS.clear()

    # The default context's singletons (glitchygames.sprites.bitmappy_sprite; audit C15)
    default_context().reset_value(slot=SINGLETONS_SLOT)


# What an inner pytest run (pytester) gets, whatever the outer run's options: pytest-randomly
# blocked, as the project's addopts block it (an inner run reads none of them). Shuffled, an
# inner run's tests ran in a new order every time, so the frames and state they left behind
# changed from run to run: driver comparisons flagged them (tests/test_frame_fingerprints.py's
# TestRecordingARun, BUGS.md #255) and tests checking inner order failed (#252)
INNER_RUN_ADDOPTS = '-p no:randomly'
# The configuration file every pytester project gets. Without one, an inner run looked for a
# configuration in the folders above the project: a temporary folder inside the repository gave
# it the repository's pyproject.toml (xdist, 100% coverage) and conftest, failing 25 tests
# (bugs/2026-11-20-driver-comparison-end-to-end-tests-fail-inside-the-repository.md). tox.ini is
# the lowest-precedence file pytest reads in a folder, so a project's own pytest.ini, or its
# pyproject.toml with [tool.pytest.ini_options], still wins; pytester's makeini writes this file.
OWN_CONFIG_FILE_NAME = 'tox.ini'
OWN_CONFIG_TEXT = '[pytest]\n'


def give_project_its_own_config(*, project: Path) -> None:
    """Give ``project`` a configuration file, so pytest's search for one stops there.

    pytest takes the first folder, going up from the run's arguments, that holds a
    configuration; its rootdir (and the conftest search) stops there too. A file the project
    already has is kept.

    Args:
        project: The project's folder.

    """
    own_config = project / OWN_CONFIG_FILE_NAME
    if not own_config.exists():
        own_config.write_text(OWN_CONFIG_TEXT, encoding='utf-8')


@pytest.fixture(autouse=True)
def inner_runs_keep_their_order(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Block pytest-randomly in every inner pytest run of a test that uses ``pytester``.

    Through ``PYTEST_ADDOPTS``, which every inner run reads (in process or as a subprocess);
    the outer run has already read it, so its own order (shuffled by ``nox -s test-random``)
    is untouched. Set after ``pytester`` is made: making it deletes ``PYTEST_ADDOPTS``, to
    keep the outer run's options out of inner runs.

    The project also gets a configuration of its own (``give_project_its_own_config``), so an
    inner run never reads the repository's when the temporary folder lies inside it.
    """
    if 'pytester' in request.fixturenames:
        pytester: pytest.Pytester = request.getfixturevalue('pytester')
        give_project_its_own_config(project=pytester.path)
        outer = os.environ.get('PYTEST_ADDOPTS', '')
        monkeypatch.setenv('PYTEST_ADDOPTS', f'{outer} {INNER_RUN_ADDOPTS}'.strip())


@pytest.fixture(autouse=True)
def restore_signal_handlers():
    """Put back the process's signal handlers after each test (tests/signal_handlers.py).

    A test that runs GameEngine.start with _shutdown mocked would otherwise leave the engine's
    exit_on_signal installed for the rest of the worker's tests.
    """
    with preserved_signal_handlers():
        yield


@pytest.fixture(autouse=True)
def faulthandler_stays_on():
    """Fail a test that leaves faulthandler off (tests/faulthandler_guard.py)."""
    with faulthandler_left_on():
        yield


@pytest.fixture(autouse=True)
def no_child_process_left_running():
    """Fail a test that leaves a process running, after stopping it (tests/child_process_guard.py).

    Every child the test starts is recorded; at teardown, after the test's own fixtures stopped
    what they started, each child still running, every process in a group one led, and every
    descendant of either is killed and named. A test killed without unwinding (a worker's
    SIGTERM) once left such processes running for days (BUGS.md #266, #275).
    """
    guard = ChildProcessGuard()
    guard.start_recording()
    yield
    leftovers = guard.stop_leftovers()
    if leftovers:
        named = '\n'.join(f'  pid {process.pid}: {process.command}' for process in leftovers)
        pytest.fail(
            f'the test left {len(leftovers)} process(es) running (now killed):\n{named}',
            pytrace=False,
        )


@pytest.fixture(autouse=True)
def in_process_clipboard():
    """Give each test an empty clipboard of its own, so none reads or writes the machine's.

    Yields:
        InProcessClipboard: The clipboard the text widgets copy to and paste from.

    """
    clipboard = InProcessClipboard()
    install_clipboard(clipboard=clipboard)
    yield clipboard
    install_clipboard(clipboard=None)


@pytest.fixture
def stand_in_ai_control_scripts(mocker):
    """Run a stand-in install's control script on every platform (tests/ai_service_stand_in.py).

    The stand-in is a POSIX shell script, which Windows can't run, so there the engine's launcher
    runs its Python twin instead; every other command, and every other platform, is untouched.
    """
    if not CONTROL_SCRIPTS_RUN_THROUGH_THEIR_TWINS:
        return
    real_run_command = process.run_command

    def run_command(*, command, environment, **options):
        if command and Path(command[0]).name == CONTROL_SCRIPT_NAME:
            twin = python_twin(control_script=Path(command[0]))
            command = [sys.executable, str(twin), *command[1:]]
            # The service's callers pass a bare environment; Windows' Python needs SYSTEMROOT
            environment = {**environment, 'SYSTEMROOT': os.environ.get('SYSTEMROOT', '')}
        return real_run_command(command=command, environment=environment, **options)

    mocker.patch.object(process, 'run_command', side_effect=run_command)


@pytest.fixture(autouse=True)
def desktop_user_files():
    """Run each test the desktop's way: no user files installed (glitchygames/user_files.py)."""
    install_user_files(user_files=None)
    yield
    install_user_files(user_files=None)


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
def empty_engine_sound_cache():
    """Start and end each test with an empty process cache of the engine's own sounds.

    The CRT power-on's sounds compile once per process (glitchygames.audio.library
    ``ENGINE_SOUND_CACHE``): without this, whether a test compiles them would depend on which
    test ran before it on the worker.
    """
    ENGINE_SOUND_CACHE.clear()
    yield
    ENGINE_SOUND_CACHE.clear()


@pytest.fixture(autouse=True)
def empty_instrument_catalog_builds():
    """Start and end each test with no catalog instrument built (``instruments.get``'s cache).

    A built instrument keeps a band-limited wave table for every band a note has read
    (``Wave.band_limited_table``): kept for the whole run, the catalog's builds held 26 MiB of
    them after the audio tests (2026-11-19, the Linux CI container), memory the Linux job's
    guard counts. Within a test a build is still shared; no module keeps one past its test.
    """
    instruments_registry._built.cache_clear()
    yield
    instruments_registry._built.cache_clear()


@pytest.fixture(autouse=True)
def empty_engine_sprite_cache():
    """Start and end each test with an empty process cache of compiled sprites.

    A sprite file's text compiles once per process (glitchygames.sprites.compiled_sprites
    ``ENGINE_SPRITE_CACHE``): without this, whether a test's load compiles would depend on which
    test ran before it on the worker. A test that leaves a compile changed fails: a compile is
    never written after it is made, so a change is a path writing around a frame's copy-on-write.
    """
    ENGINE_SPRITE_CACHE.clear()
    yield
    changed = ENGINE_SPRITE_CACHE.changed_entries()
    ENGINE_SPRITE_CACHE.clear()
    if changed:
        pytest.fail(
            'A shared sprite compile was written into (its frames are shared by every sprite '
            f'loaded from the same text; write through SpriteFrame.image or .pixels): {changed}'
        )


@pytest.fixture(autouse=True)
def restore_game_engine_class_state(monkeypatch, mocker):
    """Restore the GameEngine class attributes that engine code writes, after each test.

    The first of every test's fixtures to ask for ``mocker``, it asks for ``monkeypatch`` first,
    so ``mocker`` is always undone first. Undone the other way round, a
    ``mocker.patch.dict(os.environ)`` made after a ``monkeypatch`` change put back its snapshot,
    which held the change, after ``monkeypatch`` had undone it: 55 tests left PYTHONPATH naming a
    temporary folder, or GIT_EDITOR removed (tests/test_leaked_state_guard.py).

    The order this costs: ``mocker.patch`` then ``monkeypatch.setattr`` of the same target, where
    ``monkeypatch`` would put the patch back after ``mocker`` had put the real one back. That test
    fails here, with ``mocker``'s original left in place (``drop_patches_to_put_back``).

    GameEngine.initialize_icon stores the icon in the class attribute `icon` (each engine keeps
    its own game: `GameEngine.game` is a read-only view). A test that runs
    it with mocks (a mocked pygame.image.load) would otherwise leave the mock
    there for every later test on the worker: a real GameEngine then fails in
    initialize_system_icons with "Argument to set_icon must be a Surface". GameEngine.__init__
    also sets `USE_FASTEVENTS` on a (mocked) old pygame, which would make every later engine on
    the worker create fastevent live sources (BUGS.md #65). A test that has an engine find
    pygame started without SDL_NO_SIGNAL_HANDLERS sets `PYGAME_FOUND_WITH_SDL_SIGNAL_HANDLERS`,
    which would make every later engine warn.
    """
    for attribute_name in (
        'icon',
        'USE_FASTEVENTS',
        'PYGAME_FOUND_WITH_SDL_SIGNAL_HANDLERS',
    ):
        # Patched with its own value: whatever the test assigns is undone at teardown
        mocker.patch.object(GameEngine, attribute_name, getattr(GameEngine, attribute_name))
    yield
    patches = drop_patches_to_put_back(monkeypatch=monkeypatch, mocker=mocker)
    if patches:
        pytest.fail('\n'.join(patches), pytrace=False)


@pytest.fixture(autouse=True)
def fresh_random_streams():
    """Give each test an unseeded set of engine random streams (glitchygames.randomness).

    GameEngine and reset_streams() set the master seed and cache streams in the current engine
    context, the default one for every test (glitchygames.engine_context); without this, one
    test's seed and half-used streams would carry into the next test on the worker.
    """
    default_context().reset_value(slot=randomness.ENGINE_RANDOM_STATE_SLOT)
    yield
    default_context().reset_value(slot=randomness.ENGINE_RANDOM_STATE_SLOT)


@pytest.fixture(autouse=True)
def reset_engine_sources():
    """Give every test fresh live doors and reset them afterwards (glitchygames/sources.py).

    reset_sources() tells the installed sources (on_uninstalled), which is where a replay stops
    tracking code-posted events (Task 12), so no tracking leaks into the next test. The frame's
    polled input (glitchygames/input/state.py) is reset too: reset_sources() leaves it alone.
    So is the internal-post tracker, per engine context (glitchygames.recording: no owners,
    nothing pending), so a recorder a test left open cannot keep tracking into the next test.
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

    The active default is per engine context (glitchygames.pixel_snap) and scene setup sets it
    from Scene.PIXEL_SNAP_MODE; without this, one test's scene would change snapping for the
    next test on the worker.
    """
    pixel_snap.set_active_default_snap_mode(mode=pixel_snap.PixelSnapMode.NEAREST_HALF_UP)
    yield
    pixel_snap.set_active_default_snap_mode(mode=pixel_snap.PixelSnapMode.NEAREST_HALF_UP)


@pytest.fixture(autouse=True)
def reset_default_background_pattern():
    """Start and end each test with the canvas pattern as the default scene background.

    The default is per engine context (glitchygames.backgrounds) and GameEngine sets it from
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


@pytest.fixture(autouse=True)
def reset_engine_bookkeeping():
    """Start and end each test with none of the engine's bookkeeping kept in the default context.

    The event types --debug-events has logged as unhandled (glitchygames.events.base; audit C17)
    are logged once per engine context; without this, a type one test logged would stay silent
    in every later test on the worker. The sprite counters and breakpoints
    (glitchygames.sprites.sprite; audit C18) likewise: a breakpoint one test registered would
    stop every later test's sprites in the debugger.
    """
    default_context().reset_value(slot=UNHANDLED_EVENT_TYPES_SLOT)
    default_context().reset_value(slot=SPRITE_COUNTERS_SLOT)
    yield
    default_context().reset_value(slot=UNHANDLED_EVENT_TYPES_SLOT)
    default_context().reset_value(slot=SPRITE_COUNTERS_SLOT)


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


# The check of the process state watched since an item's setup began (tests/leaked_state_guard.py)
PROCESS_STATE_CHECK_KEY: pytest.StashKey[LeakCheck] = pytest.StashKey()


def random_is_reseeded_for_each_test(*, config: pytest.Config) -> bool:
    """Return whether pytest-randomly seeds the global random states around each test.

    Args:
        config: The run's configuration.

    Returns:
        True in a shuffled run (``nox -s test-random``).

    """
    return bool(config.getoption('randomly_reset_seed', default=False))


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> Generator[None, object, object]:
    """Watch the process's state, and start every item on the canvas.

    The watch is checked in pytest_runtest_teardown, for every item. The state an engine run
    changes is first read here, before the first item's setup.

    An item that is not a test function starts on the canvas, as every test function does. The
    canvas comes from ``ensure_pygame_graceful_quit``, an autouse fixture, and autouse fixtures
    reach only test functions: an item a collector makes (the golden replays' ``ReplayItem``,
    glitchygames/testing/replays.py) started on whatever the previous test left. A golden replay
    draws nothing on the display, so on a shuffled Windows CI worker it ended on the previous
    test's picture and the draws_frames check failed it as drawing unmarked (#283, job 5039;
    tests/test_harness_every_item_starts_on_the_canvas.py).

    Args:
        item: The test about to be set up.

    Returns:
        object: The wrapped hook's result.

    """
    if engine_written_state_for_run.cache_info().currsize == 0:
        _start_pygame_and_the_test_display()
        engine_written_state_for_run()
    if not isinstance(item, pytest.Function):
        _start_pygame_and_the_test_display()
        show_canvas()
    item.stash[PROCESS_STATE_CHECK_KEY] = watch_process_state(
        random_reseeded_for_each_test=random_is_reseeded_for_each_test(config=item.config),
        reset=functools.partial(
            reset_engine_written_state, run_state=engine_written_state_for_run()
        ),
    )
    return (yield)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_teardown(item: pytest.Item) -> Generator[None, object, object]:
    """Reset what running an engine changes, then fail a test that left other state changed.

    After every fixture's teardown, the wider ones' too (a wrapper that runs first ends last), so
    nothing that puts state back, or wrongly puts it back, is still to come. A teardown that fails
    keeps its own error, with what was left changed added to it.

    Args:
        item: The test being torn down.

    Returns:
        object: The wrapped hook's result.

    """
    try:
        result = yield
    except BaseException as error:
        leaks = end_of_item_leaks(item=item)
        if leaks:
            error.add_note(leak_message(test=item.nodeid, leaks=leaks))
        raise
    leaks = end_of_item_leaks(item=item)
    if leaks:
        pytest.fail(leak_message(test=item.nodeid, leaks=leaks), pytrace=False)
    return result


def end_of_item_leaks(*, item: pytest.Item) -> list[str]:
    """Check the state watched since setup, with what running an engine changes reset.

    Args:
        item: The test that has been torn down.

    Returns:
        What the test left changed (now put back, but for a thread); nothing for an item whose
        setup ended before its watch began.

    """
    check_process_state = item.stash.get(PROCESS_STATE_CHECK_KEY, None)
    if check_process_state is None:
        return []
    # pytest keeps every item for the whole run, and the check holds a copy of the state
    del item.stash[PROCESS_STATE_CHECK_KEY]
    return check_process_state()


@pytest.hookimpl(tryfirst=True)
def pytest_fixture_setup(fixturedef: pytest.FixtureDef[object]) -> None:
    """Start pygame and the test display before any fixture wider than one test is made.

    A module-, class-, package- or session-scoped fixture is set up before the first test that
    asks for it gets its function-scoped fixtures, ``ensure_pygame_graceful_quit`` among them, so
    without this it saw whatever display the worker's previous test left: none after a test that
    quit pygame. Zombies' module-scoped ``demo_plan`` builds a real scene, and after
    tests/test_logging.py (which ends with ``pygame.quit()``) every test of its module errored
    in setup (seed 1957271441, 2026-11-21;
    bugs/2026-11-22-a-module-fixture-ran-before-the-test-display.md).

    Args:
        fixturedef: The fixture about to be set up.

    """
    if fixturedef.scope != 'function':
        _start_pygame_and_the_test_display()


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


def busy_mixer_channels() -> list[int]:
    """Return the mixer's channels that are playing (none when the mixer is not running).

    Returns:
        Their indices.

    """
    if pygame.mixer.get_init() is None:
        return []
    return [
        index
        for index in range(pygame.mixer.get_num_channels())
        if pygame.mixer.Channel(index).get_busy()
    ]


def queued_sounds_no_live_stream_holds() -> list[str]:
    """Name each channel with a queue whose playing or queued Sound no live stream holds.

    pygame-ce 2.5.8 frees a queued Sound twice when a play lands on a channel playing one Sound
    with another queued and its table holds the only references
    (bugs/2026-11-24-pygame-mixer-frees-a-queued-sound-twice.md). Live streams hold their own
    (glitchygames/audio/live.py), so a queue only they make is safe: this finds any other
    queuer, anywhere in the suite. The holders are the current engine context's live streams,
    enumerated exactly (``LiveStreamRegistry``), so a stream of an inner context a test made and
    left queuing is named here too, as unheld. Read before the channels are silenced.

    Returns:
        One description per such channel; empty when there is none or no mixer.
    """
    if pygame.mixer.get_init() is None:
        return []
    held_chunk_ids = {
        id(chunk) for stream in live_streams_holding_chunks() for chunk in stream.held_chunks
    }
    found = []
    for index in range(pygame.mixer.get_num_channels()):
        channel = pygame.mixer.Channel(index)
        queued = channel.get_queue()
        if queued is None:
            continue
        unheld = [
            slot
            for slot, sound in (('playing', channel.get_sound()), ('queued', queued))
            if sound is not None and id(sound) not in held_chunk_ids
        ]
        if unheld:
            found.append(
                f'Sounds no live stream holds on channel {index} with a queue: {unheld} '
                '(only a live stream may queue: glitchygames/audio/live.py)'
            )
    return found


def check_every_queued_sound_is_held_by_a_live_stream() -> None:
    """Fail at once when a channel with a queue names a Sound no live stream holds."""
    found = queued_sounds_no_live_stream_holds()
    if found:
        pytest.fail('\n'.join(found))


# What each kind of unreleased stream is told to do
RELEASE_ADVICE = '(release_voice, release_every_voice, stop_now or SceneManager.terminate)'


def unreleased_live_stream_problems() -> list[str]:
    """Name every live stream of the current context that was never released, after a test.

    Releasing a stream stops its channel and lets go of every chunk, so a stream still holding
    one was never released, whatever its channel's state. The context's registry enumerates
    them exactly (``live_streams_holding_chunks``). A stream already dropped sits in a reference
    cycle with its voice, so the garbage is collected, only when the registry found something
    (a full collection costs about 44 ms), and its finalizer's report lands on this test. A
    report of a stream the registry did not find here came from a stream an earlier test on
    the worker leaked, collected only now; it is worded so.

    Returns:
        One description per unreleased stream; empty when there is none.
    """
    found_ids = {id(stream) for stream in live_streams_holding_chunks()}
    if found_ids:
        gc.collect()
    problems = [
        f'A live stream was never released ({stream.diagnostic_name}): it still holds '
        f'{len(stream.held_chunks)} chunk(s) {RELEASE_ADVICE}'
        for stream in live_streams_holding_chunks()
    ]
    for report in take_unreleased_live_stream_reports():
        if report.stream_id in found_ids:
            problems.append(
                f'A live stream was never released ({report.stream_name}): collected holding '
                f'{report.held_chunk_count} chunk(s) {RELEASE_ADVICE}'
            )
        else:
            problems.append(
                'A live stream was collected during this test; leaked by an earlier test on '
                f'this worker ({report.stream_name}): it held {report.held_chunk_count} chunk(s)'
            )
    return problems


def end_of_test_sound_problems() -> list[str]:
    """Check a test's sound as it ends, then silence the mixer; return every problem found.

    The queues are read before the channels are silenced (silencing empties them), and a
    silencing failure is added to the rest rather than raised, so no report is lost.

    Returns:
        Each problem's description; empty when the test left its sound clean.
    """
    problems = queued_sounds_no_live_stream_holds() + unreleased_live_stream_problems()
    try:
        silence_every_channel()
    except pytest.fail.Exception as failure:
        problems.append(str(failure))
    return problems


def silence_every_channel() -> None:
    """Stop every mixer channel after a test, so no sound plays on into the next one.

    Twice, as the engine stops a live voice (glitchygames/audio/live.py ``stop_now``): pygame
    starts a channel's queued sound the moment the channel is halted, so the first stop starts
    each streamed sound's queued chunk and the second stops it. One stop left a chunk playing
    into the next test, whose engine then could not partition the mixer at construction
    (BUGS.md #145's guard; tests/test_harness_silences_the_mixer.py). A channel still playing
    after both fails the test that left it (``pytest.fail``), not a later test on the worker.
    """
    if pygame.mixer.get_init() is None:
        return
    pygame.mixer.stop()
    pygame.mixer.stop()
    still_playing = busy_mixer_channels()
    if still_playing:
        pytest.fail(f'Mixer channels still playing after two stops: {still_playing}')


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
    # SDL's own default (and the engine's, unless a game opts in): no window-system messages.
    # Blocked through pygame so get_blocked tells the truth: pygame-ce reports SYSWMEVENT as
    # allowed while SDL ignores it, so a test that snapshots and restores the blocked types
    # would otherwise enable it, and real X servers then fill later tests' queues with it
    pygame.event.set_blocked(pygame.SYSWMEVENT)
    # The canvas: a test that draws nothing shows the pattern, and no test sees an earlier
    # test's drawing (the guard in pytest_runtest_call fails a test that ends on all black)
    show_canvas()

    yield

    # Every sound problem is gathered first, silencing included (end_of_test_sound_problems), and
    # reported after the rest of the teardown, so a failing check never leaves drivers behind
    sound_problems = end_of_test_sound_problems()
    restore_run_sdl_drivers(
        run_environment=SDL_DRIVER_ENVIRONMENT_FOR_RUN,
        run_state=run_sdl_driver_state,
        hides_windows=TEST_WINDOWS_HIDDEN,
    )
    with contextlib.suppress(pygame.error):
        surface = pygame.display.get_surface() if pygame.get_init() else None
        if surface is not None and surface.get_size() != TEST_DISPLAY_SIZE:
            # Shown at once: a window set_mode resizes is black until presented, and on a real
            # driver it would stay black (under the last scene's caption) while the worker waits
            # for its next test, or for the run to end
            show_canvas_on_new_display(size=TEST_DISPLAY_SIZE)
    if sound_problems:
        pytest.fail('\n'.join(sound_problems))


@pytest.fixture
def per_context_object_resets(reset_singletons, reset_engine_bookkeeping):
    """Group the resets of the objects and bookkeeping a context holds, for the leak check.

    A group of its own inside per_context_state_resets, which would otherwise take more
    arguments than the lint allows.

    Args:
        reset_singletons: Requested only to be torn down after the leak check.
        reset_engine_bookkeeping: Requested only to be torn down after the leak check.

    """


@pytest.fixture
def per_context_state_resets(
    fresh_random_streams,
    reset_engine_sources,
    reset_default_snap_mode,
    reset_default_background_pattern,
    per_context_object_resets,
):
    """Group the resets of the state the engine context holds (its slots), for the leak check.

    Args:
        fresh_random_streams: Requested only to be torn down after the leak check.
        reset_engine_sources: Requested only to be torn down after the leak check.
        reset_default_snap_mode: Requested only to be torn down after the leak check.
        reset_default_background_pattern: Requested only to be torn down after the leak check.
        per_context_object_resets: Requested only to be torn down after the leak check.

    """


@pytest.fixture
def engine_cache_resets(
    empty_engine_sound_cache, empty_engine_sprite_cache, empty_instrument_catalog_builds
):
    """Group the emptying of the engine's process caches, for the leak check.

    A group of its own inside engine_service_resets, which would otherwise take more arguments
    than the lint allows.

    Args:
        empty_engine_sound_cache: Requested only to be torn down after the leak check.
        empty_engine_sprite_cache: Requested only to be torn down after the leak check.
        empty_instrument_catalog_builds: Requested only to be torn down after the leak check.

    """


@pytest.fixture
def engine_service_resets(
    desktop_user_files,
    in_process_clipboard,
    restore_game_engine_class_state,
    engine_cache_resets,
):
    """Group the resets of the engine's other installed state, for the leak check.

    Args:
        desktop_user_files: Requested only to be torn down after the leak check.
        in_process_clipboard: Requested only to be torn down after the leak check.
        restore_game_engine_class_state: Requested only to be torn down after the leak check.
        engine_cache_resets: Requested only to be torn down after the leak check.

    """


# Requests (through the two groups above) every autouse fixture that resets or restores engine
# state, so pytest sets them up before it and tears them down after it: a leaked context is
# caught and undone before their teardowns run, so they reset the default context's state, not
# the leaked one's. Definition order cannot do this (pytest orders a plugin's autouse fixtures of
# one scope by name). A new autouse fixture must join a group, or be listed with its reason in
# tests/test_engine_context.py PROCESS_STATE_AUTOUSE_FIXTURES (the test there checks both)
@pytest.fixture(autouse=True)
def every_test_ends_in_the_default_engine_context(per_context_state_resets, engine_service_resets):
    """Fail a test that leaves another engine context current (glitchygames.engine_context).

    Every test starts in the default context. It catches a switch still entered at teardown: a
    ``context.active()`` entered by hand (``__enter__``) and never exited while something still
    holds it. A switch abandoned unexited unwinds itself when its generator is collected (its
    ``finally`` resets the context), so it is not reported. A caught leak would leave its
    context current for every later test on the worker, so it is undone before the test fails;
    if the leaked switch is collected later, its ``finally`` can reset a later test's context,
    which only happens after this test already failed (BUGS.md #228 item 2).

    Args:
        per_context_state_resets: Requested only to be torn down after this check.
        engine_service_resets: Requested only to be torn down after this check.

    """
    yield
    leaked_context = current_context()
    if leaked_context is not default_context():
        # A test-isolation reset, not an API: there is deliberately no public way to drop a
        # switch without unwinding it (glitchygames.engine_context rule 5)
        engine_context._CURRENT_CONTEXT.set(None)
        pytest.fail(f'the test left the engine context {leaked_context.name!r} current')
