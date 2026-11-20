"""Persistent save storage in the browser (IndexedDB through Emscripten's IDBFS).

Pyodide's filesystem is in memory: files written under ``Path.home()`` (where glitchygames.state
keeps saves on this platform: ~/.local/share/<app>) vanish when the page reloads. IDBFS keeps a
directory in IndexedDB, but only when told: ``FS.syncfs(True)`` loads it into memory before use,
``FS.syncfs(False)`` writes changes back. browser/boot.py mounts it before the game starts (over
the saves' folder and the sound cache's), flushes after every save (glitchygames.state
``observe_disk_save_changes``) and every burst of written sounds (glitchygames.audio.disk_cache
``observe_sound_writes``, through ``flush_soon``), and when the page is hidden. Verified across
reloads in Chromium and WebKit (../pygame-ce-wasm, results V1-*).
"""

import asyncio
from pathlib import Path

import js
import pyodide_js
from pyodide.ffi import create_once_callable, create_proxy, jsnull

file_system = pyodide_js.FS

# Flushes started without waiting for them (flush_in_background). Kept until done: the event
# loop holds only weak references to tasks, and one nobody holds can be collected mid-flush
_pending_flushes: set[asyncio.Task[str | None]] = set()

# flush_soon's one flush at a time: 'scheduled' (not started yet: a request joins it), 'running'
# (a request asks for one more pass after it), 'again' (that pass is owed)
_sound_flush_state: set[str] = set()


async def _sync(*, populate: bool) -> str | None:
    """Run FS.syncfs and wait for its callback.

    Returns:
        None on success, else the error text.
    """
    future = asyncio.get_running_loop().create_future()

    def done(error: object = None) -> None:
        # Emscripten passes JS null (pyodide.ffi.jsnull in Python) on success
        if not future.done():
            future.set_result(None if error is None or error is jsnull else str(error))

    file_system.syncfs(populate, create_once_callable(done))
    return await future


async def mount_persistent_directory(path: str) -> dict:
    """Mount IDBFS at `path` and load what earlier page loads stored there.

    Returns:
        What happened, for the probe log.
    """
    # In memory (Pyodide's MEMFS): nothing here blocks
    Path(path).mkdir(parents=True, exist_ok=True)  # ruff: ignore[blocking-path-method-in-async-function]
    report: dict = {'path': path}
    try:
        file_system.mount(file_system.filesystems.IDBFS, js.Object.new(), path)
        report['mounted'] = True
    except Exception as error:  # ruff: ignore[blind-except] - report every failure
        report['mounted'] = f'FAILED: {type(error).__name__}: {error}'
        return report
    report['load_error'] = await _sync(populate=True)
    return report


async def flush() -> str | None:
    """Write every mounted IDBFS directory back to IndexedDB.

    Returns:
        None on success, else the error text.
    """
    return await _sync(populate=False)


def flush_in_background() -> None:
    """Start a flush without waiting for it (kept referenced until it finishes)."""
    task = asyncio.ensure_future(flush())
    _pending_flushes.add(task)
    task.add_done_callback(_pending_flushes.discard)


def flush_soon() -> None:
    """Flush soon, with at most one such flush in flight: one write-back for a burst of requests.

    Sounds are written one at a time, across a scene's setup and later frames, and each asks to
    flush. A request with nothing scheduled schedules a flush for the event loop's next turn; a
    request while one is scheduled joins it; a request while one is running asks for one more
    pass once it ends (its files changed after the running pass may have read them). So no two
    of these FS.syncfs calls overlap, and none of the requested changes is left unwritten.
    """
    if 'scheduled' in _sound_flush_state:
        return
    if 'running' in _sound_flush_state:
        _sound_flush_state.add('again')
        return
    _sound_flush_state.add('scheduled')
    asyncio.get_running_loop().call_soon(_start_sound_flush)


def _start_sound_flush() -> None:
    _sound_flush_state.discard('scheduled')
    _sound_flush_state.add('running')
    task = asyncio.ensure_future(_sound_flush_passes())
    _pending_flushes.add(task)
    task.add_done_callback(_pending_flushes.discard)


async def _sound_flush_passes() -> str | None:
    """Flush, and flush again while requests arrived during the last pass.

    Returns:
        The last pass's error text, or None.
    """
    try:
        while True:
            _sound_flush_state.discard('again')
            error = await flush()
            if 'again' not in _sound_flush_state:
                return error
    finally:
        _sound_flush_state.discard('running')


def flush_on_page_hide() -> None:
    """Start a flush when the page is hidden or unloaded (best effort: it is asynchronous)."""

    def on_hide(_event: object) -> None:
        flush_in_background()

    handler = create_proxy(on_hide)
    js.window.addEventListener('pagehide', handler)
    js.document.addEventListener('visibilitychange', handler)
