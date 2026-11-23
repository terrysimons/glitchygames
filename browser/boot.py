"""Start a GlitchyGames game in the browser (PyScript `<script type="py">`, main thread).

The page (browser/index.html, rendered by `python -m scripts.build_browser_bundle`) loads
Pyodide with GlitchyGames' own pygame-ce wheel (the fork's build: plans/2026-10-23-game-host-and-browser-runner.md)
and unpacks the engine and the game's member packages (glitchygames.zip, then one archive per
member package the game needs, as the bundle's pyscript.toml lists them) into the working
directory. This bootstrap then:

1. gives SDL the page's canvas;
2. mounts IndexedDB-backed storage over ~/.local/share, where glitchygames.state keeps saves on
   this platform, and over the sound cache's root (``sound_cache_root()``: ~/.cache/glitchygames
   here), where compiled sounds are kept, so a later visit reads them instead of compiling; loads
   what earlier visits stored, and flushes after every save (``observe_disk_save_changes``),
   after each burst of written sounds (``observe_sound_writes``) and when the page is hidden;
   installs the page's clipboard
   (browser_clipboard.py) and the player's own files (browser_user_files.py: a file picker to
   open, downloads to save);
   In a measurement build (``frame_probe`` in boot_config.json) it also installs the
   frame-phase probe (``install_frame_probe``);
3. waits for a click on the page (browsers start audio only after a user gesture);
4. runs the game with ``GameEngine.start_async``, one outer tick per animation frame: the game
   host's ``TickPacer`` runs a frame on every whole number of display ticks when the target
   period is that close (60 FPS: every tick at 60 Hz, every second at 120 Hz, so frames follow
   the display), and otherwise averages the target FPS (60 FPS on 144 Hz).

It runs only in the browser (it imports Pyodide's ``js`` and ``pyodide_js``), outside the package
and its desktop test suite.
"""

import asyncio
import importlib
import json
import logging
import sys
from pathlib import Path

import browser_clipboard
import browser_storage
import browser_user_files
import js
import pyodide_js
from pyodide.ffi import create_once_callable, create_proxy

LOG = logging.getLogger('game.browser')
BOOT_CONFIG_PATH = Path('boot_config.json')
SAVE_ROOT = Path.home() / '.local' / 'share'
# Where files the player opens through the file picker are copied
OPENED_FILES_DIRECTORY = Path.home() / 'opened'
# The engine's own format (GameEngine.initialize_arguments' basicConfig)
LOG_FORMAT = '%(name)s - %(levelname)s - %(message)s'


class AnimationFrameTicks:
    """Outer ticks for the game host: one per requestAnimationFrame callback (one proxy)."""

    def __init__(self) -> None:
        """Make the callback proxy (kept for the whole run)."""
        self._pending: asyncio.Future[float] | None = None
        self._callback = create_proxy(self._on_animation_frame)

    def _on_animation_frame(self, timestamp_milliseconds: float) -> None:
        if self._pending is not None and not self._pending.done():
            self._pending.set_result(timestamp_milliseconds / 1000.0)

    async def wait_for_tick(self) -> float:
        """Wait for the next animation frame.

        Returns:
            Its timestamp in seconds (the browser's monotonic frame clock).

        """
        self._pending = asyncio.get_running_loop().create_future()
        js.window.requestAnimationFrame(self._callback)
        return await self._pending

    def destroy(self) -> None:
        """Release the callback proxy."""
        self._callback.destroy()


def set_status(text: str) -> None:
    """Show ``text`` in the page's status line (and the log)."""
    element = js.document.getElementById('status')
    if element is not None:
        element.textContent = text
    LOG.info(text)


async def wait_for_click() -> None:
    """Show the start overlay and wait until the player clicks or presses a key on the page."""
    overlay = js.document.getElementById('start-overlay')
    clicked: asyncio.Future[None] = asyncio.get_running_loop().create_future()

    def start(_event: object) -> None:
        if not clicked.done():
            clicked.set_result(None)

    handler = create_once_callable(start)
    overlay.style.display = 'flex'
    overlay.addEventListener('click', handler, js.Object.fromEntries([['once', True]]))
    await clicked
    overlay.style.display = 'none'


def flush_soon(_path: Path) -> None:
    """Flush the save storage after a save (called by glitchygames.state; does not wait)."""
    browser_storage.flush_in_background()


def flush_after_written_sounds(_path: Path) -> None:
    """Flush the sound cache once a burst of written sounds is over (glitchygames.audio)."""
    browser_storage.flush_soon()


def read_boot_config() -> dict[str, object]:
    """Read boot_config.json (written by `python -m scripts.build_browser_bundle`).

    Returns:
        The game, its module and scene class, title and command-line arguments.

    """
    return json.loads(BOOT_CONFIG_PATH.read_text(encoding='utf-8'))


def install_masterhub_bridge() -> None:
    """Register bitmappy's MasterHUB web-hub bridge, when this bundle ships it (bitmappy only).

    The bridge (masterhub_bridge.py) and bitmappy.masterhub ship only in the bitmappy bundle, so a
    missing ``masterhub_bridge`` module just means "not this game" and is skipped. Any other import
    error -- a real break inside the bridge or the seam -- propagates instead of being swallowed
    into a silent no-op (the failure mode that once hid a bug), and each path logs one line.

    Raises:
        ModuleNotFoundError: If importing the bridge or the seam fails for any reason other than
            the bridge module simply not being shipped in this bundle.

    """
    try:
        import masterhub_bridge

        from bitmappy.masterhub import install_masterhub
    except ModuleNotFoundError as error:
        if error.name != 'masterhub_bridge':
            raise
        LOG.info('No MasterHUB bridge in this bundle; the hub mirror is off')
        return
    install_masterhub(installer=masterhub_bridge.install)
    LOG.info('MasterHUB bridge registered; the hub mirror is active')


def install_frame_probe(*, config: dict[str, object]) -> None:
    """Install the frame-phase probe when boot_config.json asks for one (a measurement build).

    Only ``python -m scripts.measure_browser_frames`` writes ``frame_probe`` (its settings) and
    copies ``frame_phase_probe.py`` beside this file; a normal bundle has neither, and this does
    nothing. The probe prints its report to the console (scripts/frame_phase_probe.py).
    """
    settings = config.get('frame_probe')
    if settings is None:
        return
    import frame_phase_probe

    frame_phase_probe.install_in_browser(settings=settings, emit=print)
    LOG.info('Frame-phase probe installed: %s', settings)


async def main() -> None:
    """Boot the configured game and run it until it ends."""
    # Standard output reaches only the browser console; PyScript shows anything written to
    # standard error on the page itself. The engine's own basicConfig then finds this handler
    # and does nothing, so the engine's --log-level is applied below, once it is parsed
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format=LOG_FORMAT)
    config = read_boot_config()
    set_status(f'Loading {config["title"]}...')

    pyodide_js.canvas.setCanvas2D(js.document.getElementById('canvas'))

    storage_report = await browser_storage.mount_persistent_directory(str(SAVE_ROOT))
    LOG.info('Save storage: %s', storage_report)
    from glitchygames.audio.disk_cache import observe_sound_writes, sound_cache_root

    sound_root = sound_cache_root()
    if sound_root is not None:
        sound_report = await browser_storage.mount_persistent_directory(str(sound_root))
        LOG.info('Sound cache storage: %s', sound_report)
        observe_sound_writes(observer=flush_after_written_sounds)
    browser_storage.flush_on_page_hide()

    # The engine parses its command line when it is constructed
    sys.argv = [config['game'], *config.get('arguments', [])]
    module = importlib.import_module(config['module'])
    game_class = getattr(module, config['scene_class'])

    from glitchygames.clipboard import install_clipboard
    from glitchygames.engine import GameEngine
    from glitchygames.state.manager import observe_disk_save_changes
    from glitchygames.user_files import install_user_files

    observe_disk_save_changes(observer=flush_soon)
    install_clipboard(clipboard=browser_clipboard.BrowserClipboard())
    install_user_files(
        user_files=browser_user_files.BrowserUserFiles(directory=OPENED_FILES_DIRECTORY)
    )
    install_masterhub_bridge()  # bitmappy's hub mirror (skipped in bundles without the bridge)
    install_frame_probe(config=config)  # a measurement build's probe (nothing otherwise)

    set_status(f'{config["title"]}: click to play')
    await wait_for_click()
    set_status(config['title'])

    ticks = AnimationFrameTicks()
    try:
        engine = GameEngine(game=game_class)
        # The engine's own options (C8), not GameEngine.OPTIONS, the current game's view
        logging.getLogger().setLevel(engine.options['log_level'].upper())
        await engine.start_async(wait_for_tick=ticks.wait_for_tick)
        set_status(f'{config["title"]} ended. Reload the page to play again.')
    except SystemExit as exit_request:
        set_status(f'{config["title"]} ended (exit {exit_request.code}). Reload to play again.')
    finally:
        ticks.destroy()
        await browser_storage.flush()


await main()  # ruff: ignore[yield-outside-function, await-outside-async] - PyScript runs this file in its event loop
