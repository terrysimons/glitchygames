"""The browser page's persistent storage (browser/browser_storage.py), on the desktop.

The module runs only in Pyodide: it imports ``js``, ``pyodide_js`` and ``pyodide.ffi``. These
tests load it with stand-ins built from Emscripten's contract for ``FS.syncfs(populate,
callback)``: the work is asynchronous, and the callback is called once, with JS null (Pyodide's
``jsnull``) on success or an error object. The stand-in finishes a write-back only when a test
says so (``finish_one``), so no wall-clock time decides an outcome. Only ``flush_soon``'s
scheduling is tested here; the storage itself was checked across reloads in Chromium and WebKit
(the branch's pull request).
"""

from __future__ import annotations

import asyncio
import importlib.util
import types
from typing import TYPE_CHECKING

from tests.harness import PROJECT_ROOT

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

BROWSER_STORAGE_PATH = PROJECT_ROOT / 'browser' / 'browser_storage.py'
# Event-loop turns a test may take to settle; past it the test fails loudly instead of hanging
TURN_LIMIT = 1000


class StandInFileSystem:
    """Emscripten's FS as far as browser_storage uses it: syncfs, asynchronous, counted.

    ``syncfs`` returns at once and keeps the callback; ``finish_one`` calls the oldest pending
    callback (once, with JS null), from the event loop as Emscripten does, never inside syncfs.
    """

    def __init__(self, *, jsnull: object) -> None:
        """Start with no write-backs."""
        self._jsnull = jsnull
        self.write_backs = 0
        self.in_flight = 0
        self.most_in_flight = 0
        self.pending_callbacks: list[Callable[[object], None]] = []

    def syncfs(self, populate: bool, callback: Callable[[object], None]) -> None:  # ruff: ignore[boolean-type-hint-positional-argument] - Emscripten's positional signature
        """Start a write-back (populate False); it finishes when finish_one is called."""
        assert populate is False
        self.write_backs += 1
        self.in_flight += 1
        self.most_in_flight = max(self.most_in_flight, self.in_flight)

        self.pending_callbacks.append(callback)

    def finish_one(self) -> None:
        """Finish the oldest pending write-back: its callback runs on the event loop's next turn."""
        callback = self.pending_callbacks.pop(0)
        self.in_flight -= 1
        asyncio.get_running_loop().call_soon(callback, self._jsnull)


def load_browser_storage(*, mocker: MockerFixture) -> tuple[types.ModuleType, StandInFileSystem]:
    """Load browser/browser_storage.py with Pyodide's modules stood in for.

    Returns:
        The module and its stand-in file system.

    """
    jsnull = object()
    file_system = StandInFileSystem(jsnull=jsnull)
    pyodide_ffi = types.ModuleType('pyodide.ffi')
    pyodide_ffi.create_once_callable = lambda function: function
    pyodide_ffi.create_proxy = lambda function: function
    pyodide_ffi.jsnull = jsnull
    pyodide = types.ModuleType('pyodide')
    pyodide.ffi = pyodide_ffi
    pyodide_js = types.ModuleType('pyodide_js')
    pyodide_js.FS = file_system
    mocker.patch.dict(
        'sys.modules',
        {
            'js': types.ModuleType('js'),
            'pyodide': pyodide,
            'pyodide.ffi': pyodide_ffi,
            'pyodide_js': pyodide_js,
        },
    )
    specification = importlib.util.spec_from_file_location('browser_storage', BROWSER_STORAGE_PATH)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module, file_system


async def run_until(condition: Callable[[], bool]) -> None:
    """Give the event loop turns until the condition holds.

    Raises:
        AssertionError: If it does not hold within TURN_LIMIT turns.
    """
    for _ in range(TURN_LIMIT):
        if condition():
            return
        await asyncio.sleep(0)
    message = f'the condition did not hold within {TURN_LIMIT} event-loop turns'
    raise AssertionError(message)


async def settle(*, storage: types.ModuleType, file_system: StandInFileSystem) -> None:
    """Finish write-backs as they start, until no flush is scheduled, running or pending.

    Raises:
        AssertionError: If it has not settled within TURN_LIMIT turns.
    """
    for _ in range(TURN_LIMIT):
        await asyncio.sleep(0)
        if file_system.pending_callbacks:
            file_system.finish_one()
        elif not storage._sound_flush_state and not storage._pending_flushes:
            return
    message = f'storage did not settle within {TURN_LIMIT} event-loop turns'
    raise AssertionError(message)


def test_a_burst_of_requests_in_one_turn_is_one_write_back(mocker: MockerFixture) -> None:
    """A scene's setup writing ten sounds at once asks ten times and flushes once."""
    storage, file_system = load_browser_storage(mocker=mocker)

    async def burst() -> None:
        for _ in range(10):
            storage.flush_soon()
        await settle(storage=storage, file_system=file_system)

    asyncio.run(burst())

    assert file_system.write_backs == 1


def test_requests_while_a_flush_runs_get_one_more_pass_and_never_overlap(
    mocker: MockerFixture,
) -> None:
    """Sounds written while a write-back runs are written by one more pass after it.

    Writes spread over several event-loop turns once started one write-back per turn, eight in
    flight at once in Chromium ("8 FS.syncfs operations in flight at once").
    """
    storage, file_system = load_browser_storage(mocker=mocker)

    async def spread_out() -> None:
        storage.flush_soon()
        await run_until(lambda: len(file_system.pending_callbacks) == 1)  # the pass is running
        for _ in range(5):
            storage.flush_soon()  # during the running pass: one more pass owed
            await asyncio.sleep(0)
        assert file_system.write_backs == 1  # none started while the first is unfinished
        file_system.finish_one()
        await settle(storage=storage, file_system=file_system)

    asyncio.run(spread_out())

    assert file_system.most_in_flight == 1
    assert file_system.write_backs == 2


def test_after_everything_settles_a_new_request_flushes_again(mocker: MockerFixture) -> None:
    """Nothing is left marked as running or owed: the next burst is written too."""
    storage, file_system = load_browser_storage(mocker=mocker)

    async def two_bursts() -> None:
        storage.flush_soon()
        await settle(storage=storage, file_system=file_system)
        storage.flush_soon()
        await settle(storage=storage, file_system=file_system)

    asyncio.run(two_bursts())

    assert file_system.write_backs == 2
    assert file_system.most_in_flight == 1
