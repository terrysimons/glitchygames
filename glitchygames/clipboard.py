"""The clipboard text widgets copy to and paste from, chosen for the platform.

- ``PyperclipClipboard``: the desktop's own clipboard, through pyperclip (pbcopy and pbpaste on
  macOS, the Windows API, xclip, xsel or wl-clipboard on Linux).
- ``InProcessClipboard``: text held by this process alone, where pyperclip is not installed.
- A browser build installs its own (browser/browser_clipboard.py) with ``install_clipboard``:
  pyperclip installs in Pyodide but cannot work there, since it runs the platform's clipboard
  programs and a page cannot start a process ("Pyperclip could not find a copy/paste
  mechanism", measured 2026-10-24 in Chromium 141 and WebKit 26).

``system_clipboard()`` returns the installed clipboard, or the one ``create_clipboard()``
chooses, made when first needed.
"""

from __future__ import annotations

import importlib
import logging
from typing import Protocol, Self

LOG = logging.getLogger('game.clipboard')
LOG.addHandler(logging.NullHandler())


class ClipboardUnavailableError(Exception):
    """The clipboard could not be read or written (no clipboard program on this machine)."""


class Clipboard(Protocol):
    """Where copied text goes and pasted text comes from."""

    def copy(self, text: str) -> None:
        """Put ``text`` on the clipboard.

        Raises:
            ClipboardUnavailableError: If the clipboard cannot be written.

        """
        ...

    def paste(self) -> str:
        """Return the clipboard's text ('' when it holds none).

        Raises:
            ClipboardUnavailableError: If the clipboard cannot be read.

        """
        ...


class InProcessClipboard:
    """A clipboard that only this process sees: text copied here pastes here."""

    def __init__(self: Self) -> None:
        """Start empty."""
        self.text = ''

    def copy(self: Self, text: str) -> None:
        """Hold ``text``."""
        self.text = text

    def paste(self: Self) -> str:
        """Return the text held last.

        Returns:
            The text, or '' before anything was copied.

        """
        return self.text


class PyperclipClipboard:
    """The desktop's clipboard, through pyperclip."""

    def __init__(self: Self) -> None:
        """Import pyperclip (ImportError where it is not installed: ``create_clipboard``)."""
        self._pyperclip = importlib.import_module('pyperclip')

    def copy(self: Self, text: str) -> None:
        """Put ``text`` on the desktop's clipboard.

        Raises:
            ClipboardUnavailableError: If pyperclip finds no clipboard program (headless Linux
                without xclip, xsel or wl-clipboard).

        """
        try:
            self._pyperclip.copy(text)
        except self._pyperclip.PyperclipException as error:
            raise ClipboardUnavailableError(str(error)) from error

    def paste(self: Self) -> str:
        """Return the desktop clipboard's text.

        Returns:
            The text ('' when it holds none).

        Raises:
            ClipboardUnavailableError: If pyperclip finds no clipboard program.

        """
        try:
            return self._pyperclip.paste()
        except self._pyperclip.PyperclipException as error:
            raise ClipboardUnavailableError(str(error)) from error


def create_clipboard() -> Clipboard:
    """Choose this platform's clipboard: the desktop's through pyperclip, else in-process.

    Returns:
        The clipboard.

    """
    try:
        return PyperclipClipboard()
    except ImportError:
        LOG.info('pyperclip is not installed: copied text stays inside this program')
        return InProcessClipboard()


class _ClipboardRegistry:
    """The process's one clipboard: installed, or chosen when first needed (None until then)."""

    def __init__(self: Self) -> None:
        """Start with no clipboard."""
        self.clipboard: Clipboard | None = None


_REGISTRY = _ClipboardRegistry()


def install_clipboard(*, clipboard: Clipboard | None) -> None:
    """Make ``clipboard`` the one ``system_clipboard()`` returns (None: choose again when needed).

    Args:
        clipboard: The clipboard (a browser's), or None.

    """
    _REGISTRY.clipboard = clipboard


def system_clipboard() -> Clipboard:
    """Return the installed clipboard, choosing one (``create_clipboard``) the first time.

    Returns:
        The clipboard.

    """
    if _REGISTRY.clipboard is None:
        _REGISTRY.clipboard = create_clipboard()
    return _REGISTRY.clipboard
