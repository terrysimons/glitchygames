"""Start a GlitchyGames game in the browser (PyScript `<script type="py">`, main thread).

The page (browser/index.html, rendered by scripts/build_browser_bundle.py) loads Pyodide with
GlitchyGames' own pygame-ce wheel (the fork's build: plans/2026-10-23-game-host-and-browser-runner.md)
and unpacks the engine into the working directory. This bootstrap then:

1. gives SDL the page's canvas;
2. mounts IndexedDB-backed storage over ~/.local/share, where glitchygames.state keeps saves on
   this platform, loads what earlier visits stored, and flushes after every save
   (``observe_disk_save_changes``) and when the page is hidden; installs the page's clipboard
   (browser_clipboard.py) and the player's own files (browser_user_files.py: a file picker to
   open, downloads to save);
3. waits for a click on the page (browsers start audio only after a user gesture);
4. runs the game with ``GameEngine.start_async``, one outer tick per animation frame: the game
   host paces inner frames at the game's target FPS whatever the display's refresh rate.

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


def read_boot_config() -> dict[str, object]:
    """Read boot_config.json (written by scripts/build_browser_bundle.py).

    Returns:
        The game, its module and scene class, title and command-line arguments.

    """
    return json.loads(BOOT_CONFIG_PATH.read_text(encoding='utf-8'))


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

    set_status(f'{config["title"]}: click to play')
    await wait_for_click()
    set_status(config['title'])

    ticks = AnimationFrameTicks()
    try:
        engine = GameEngine(game=game_class)
        logging.getLogger().setLevel(GameEngine.OPTIONS['log_level'].upper())
        await engine.start_async(wait_for_tick=ticks.wait_for_tick)
        set_status(f'{config["title"]} ended. Reload the page to play again.')
    except SystemExit as exit_request:
        set_status(f'{config["title"]} ended (exit {exit_request.code}). Reload to play again.')
    finally:
        ticks.destroy()
        await browser_storage.flush()


await main()  # ruff: ignore[yield-outside-function, await-outside-async] - PyScript runs this file in its event loop
