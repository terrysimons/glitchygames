"""The clipboard factory (glitchygames/clipboard.py): the platform's clipboard, or our own."""

from __future__ import annotations

import sys

import pyperclip
import pytest

from glitchygames.clipboard import (
    ClipboardUnavailableError,
    InProcessClipboard,
    PyperclipClipboard,
    create_clipboard,
    install_clipboard,
    system_clipboard,
)


class TestInProcessClipboard:
    """Text copied in this process pastes in this process."""

    def test_it_starts_empty(self):
        assert not InProcessClipboard().paste()

    def test_it_pastes_what_was_copied_last(self):
        clipboard = InProcessClipboard()

        clipboard.copy('first')
        clipboard.copy('second')

        assert clipboard.paste() == 'second'


class TestPyperclipClipboard:
    """The desktop's clipboard through pyperclip (patched: no test touches the machine's)."""

    def test_copy_and_paste_go_through_pyperclip(self, mocker):
        copy = mocker.patch.object(pyperclip, 'copy')
        mocker.patch.object(pyperclip, 'paste', return_value='on the desktop')
        clipboard = PyperclipClipboard()

        clipboard.copy('copied')

        copy.assert_called_once_with('copied')
        assert clipboard.paste() == 'on the desktop'

    @pytest.mark.parametrize('operation', ['copy', 'paste'])
    def test_no_clipboard_program_is_an_unavailable_clipboard(self, mocker, operation):
        """Without xclip, xsel or wl-clipboard (headless Linux), pyperclip raises its own error."""
        no_mechanism = pyperclip.PyperclipException('no copy/paste mechanism')
        mocker.patch.object(pyperclip, 'copy', side_effect=no_mechanism)
        mocker.patch.object(pyperclip, 'paste', side_effect=no_mechanism)
        clipboard = PyperclipClipboard()
        arguments = ('text',) if operation == 'copy' else ()

        with pytest.raises(ClipboardUnavailableError, match='no copy/paste mechanism') as raised:
            getattr(clipboard, operation)(*arguments)

        assert raised.value.__cause__ is no_mechanism


class TestCreateClipboard:
    """The factory picks pyperclip when it is installed, else the process's own clipboard."""

    def test_with_pyperclip_it_is_the_desktop_clipboard(self):
        assert isinstance(create_clipboard(), PyperclipClipboard)

    def test_without_pyperclip_it_is_the_process_clipboard(self, mocker, caplog):
        # A None entry makes the import fail, as where pyperclip is not installed
        mocker.patch.dict(sys.modules, {'pyperclip': None})

        with caplog.at_level('INFO', logger='game.clipboard'):
            clipboard = create_clipboard()

        assert isinstance(clipboard, InProcessClipboard)
        assert 'pyperclip is not installed' in caplog.text


class TestSystemClipboard:
    """The installed clipboard, else the factory's choice, made once."""

    def test_it_is_the_installed_clipboard(self):
        clipboard = InProcessClipboard()

        install_clipboard(clipboard=clipboard)

        assert system_clipboard() is clipboard

    def test_without_one_installed_it_chooses_once(self, mocker):
        mocker.patch.dict(sys.modules, {'pyperclip': None})
        install_clipboard(clipboard=None)

        chosen = system_clipboard()

        assert isinstance(chosen, InProcessClipboard)
        assert system_clipboard() is chosen
