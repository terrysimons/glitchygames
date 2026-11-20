"""The player's own files in the browser: a file picker to open, downloads to save.

The game's files live in Pyodide's in-memory file system, which the player cannot see
(glitchygames/user_files.py). browser/boot.py installs ``BrowserUserFiles``:

- ``open_file`` shows the browser's file picker; the chosen file is copied into
  ``directory`` and handed to the game between frames.
- ``save_file`` hands a file the game saved to the player as a download.

Both start from the game's frame, a frame after the player's click. Measured 2026-10-24 in
Chromium 141 and WebKit 26 (../pygame-ce-wasm, the clipboard probe): the picker opens and the
download starts there; the click still counts as the player's gesture.
"""

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import js
from pyodide.ffi import create_once_callable, create_proxy, to_js

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

LOG = logging.getLogger('game.browser')

# How long a download's object URL is kept before it is released: the browser reads the file
# after the click returns
DOWNLOAD_URL_LIFETIME_MILLISECONDS = 60_000


class BrowserUserFiles:
    """Opens the player's files through the file picker and saves through downloads."""

    def __init__(self, *, directory: Path) -> None:
        """Copy opened files into ``directory``.

        Args:
            directory: Where opened files are copied (in Pyodide's file system).

        """
        self.directory = directory
        # Copies in flight: the event loop holds only weak references to tasks
        self._pending_copies: set[asyncio.Task[None]] = set()

    def open_file(
        self, *, accepted_extensions: Sequence[str], on_opened: Callable[[Path], None]
    ) -> None:
        """Show the file picker; ``on_opened`` gets the chosen file's copy (never if cancelled)."""
        file_input = js.document.createElement('input')
        file_input.type = 'file'
        file_input.accept = ','.join(accepted_extensions)

        def release(_event: object = None) -> None:
            chosen_listener.destroy()
            cancel_listener.destroy()

        def chosen(_event: object) -> None:
            files = file_input.files
            if files.length:
                task = asyncio.ensure_future(
                    self._copy_in(chosen_file=files.item(0), on_opened=on_opened)
                )
                self._pending_copies.add(task)
                task.add_done_callback(self._pending_copies.discard)
            release()

        chosen_listener = create_proxy(chosen)
        cancel_listener = create_proxy(release)
        file_input.addEventListener('change', chosen_listener)
        file_input.addEventListener('cancel', cancel_listener)
        file_input.click()

    async def _copy_in(self, *, chosen_file: object, on_opened: Callable[[Path], None]) -> None:
        contents = await chosen_file.arrayBuffer()
        # Only the name: a browser gives no directories, but the name is the player's text
        path = self.directory / Path(chosen_file.name).name
        self.directory.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents.to_bytes())
        LOG.info('Opened %s (%d bytes)', path.name, contents.byteLength)
        on_opened(path)

    def save_file(self, *, path: Path) -> None:
        """Download the file the game saved at ``path``, under its name."""
        contents = Path(path).read_bytes()
        array = js.Uint8Array.new(len(contents))
        array.assign(contents)
        blob = js.Blob.new(
            to_js([array]),
            to_js({'type': 'application/octet-stream'}, dict_converter=js.Object.fromEntries),
        )
        url = js.URL.createObjectURL(blob)
        anchor = js.document.createElement('a')
        anchor.href = url
        anchor.download = Path(path).name
        anchor.click()
        js.setTimeout(
            create_once_callable(lambda: js.URL.revokeObjectURL(url)),
            DOWNLOAD_URL_LIFETIME_MILLISECONDS,
        )
        LOG.info('Downloading %s (%d bytes)', anchor.download, len(contents))
