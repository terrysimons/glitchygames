"""The page's clipboard for the engine's text widgets (installed by browser/boot.py).

pyperclip cannot work in a page: it runs the platform's clipboard programs, and a page cannot
start a process (glitchygames/clipboard.py). Measured 2026-10-24 in Chromium 141 and WebKit 26
(../pygame-ce-wasm, the clipboard probe):

- Paste: Ctrl/Cmd+V fires the page's paste event, with its text, before the game's next frame
  reads the key (SDL leaves a keydown's default action alone while text input is on: SDL 2.32.10
  ``Emscripten_HandleKey``). The text is kept, and ``paste()`` returns it. No permission needed.
- Copy: the text is kept (it pastes inside the game) and written to the system clipboard with
  ``navigator.clipboard.writeText``. Chromium allows that a frame after the key; Safari refuses
  it outside the key's own handler (NotAllowedError), so there copied text stays in the game.
"""

import logging

import js
from pyodide.ffi import create_proxy

from glitchygames.clipboard import InProcessClipboard

LOG = logging.getLogger('game.browser')


class BrowserClipboard(InProcessClipboard):
    """Pastes what the page's paste event carried; copies to the system clipboard when allowed."""

    def __init__(self) -> None:
        """Listen for the page's paste events (for the whole run)."""
        super().__init__()
        self._paste_listener = create_proxy(self._on_paste)
        self._write_refused_listener = create_proxy(self._on_write_refused)
        js.document.addEventListener('paste', self._paste_listener)

    def _on_paste(self, event: object) -> None:
        text = event.clipboardData.getData('text/plain')
        if text:
            self.text = text

    def _on_write_refused(self, error: object) -> None:
        LOG.info(
            'The browser refused the system clipboard (%s): copied text pastes in the game', error
        )

    def copy(self, text: str) -> None:
        """Keep ``text``, and put it on the system clipboard where the browser allows it."""
        super().copy(text)
        # Absent outside a secure context (a page served over plain HTTP from another machine)
        system_clipboard = getattr(js.navigator, 'clipboard', None)
        if system_clipboard is None:
            return
        system_clipboard.writeText(text).catch(self._write_refused_listener)
