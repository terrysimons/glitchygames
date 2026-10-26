"""Bitmappy where the game's files are not the player's (a browser: glitchygames/user_files.py)."""

from __future__ import annotations

import shutil

from brave_adventurer_papyrus.constants import SPRITES_DIR as PAPYRUS_SPRITES_DIRECTORY
from glitchygames.user_files import install_user_files

# A real sprite file, named 'scarab' in its [sprite] table
SPRITE_FILE = PAPYRUS_SPRITES_DIRECTORY / 'scarab.toml'


class RecordingUserFiles:
    """Stands in for a browser's user files: records what the editor asks the player for."""

    def __init__(self):
        """Start with no requests."""
        self.open_requests = []

    def open_file(self, *, accepted_extensions, on_opened):
        self.open_requests.append((tuple(accepted_extensions), on_opened))

    def save_file(self, *, path):
        raise AssertionError(path)


class TestLoadThroughUserFiles:
    """Load asks the player for one of their own files instead of a typed name."""

    def test_load_opens_the_players_file_picker_for_sprite_files(self, bitmap_editor):
        user_files = RecordingUserFiles()
        install_user_files(user_files=user_files)
        scene_before = bitmap_editor.next_scene

        bitmap_editor.on_load_dialog_event(None)

        ((accepted_extensions, on_opened),) = user_files.open_requests
        assert accepted_extensions == ('.toml',)
        assert on_opened == bitmap_editor.load_opened_file
        assert bitmap_editor.next_scene is scene_before

    def test_without_user_files_load_asks_for_a_name(self, bitmap_editor):
        """The desktop's way: the Load dialog."""
        bitmap_editor.on_load_dialog_event(None)

        assert type(bitmap_editor.next_scene).__name__ == 'LoadDialogScene'

    def test_the_opened_file_is_loaded_into_the_canvas(self, bitmap_editor, tmp_path):
        """What the picker copied in is loaded as the canvas's sprite."""
        opened_copy = tmp_path / 'from the player.toml'
        shutil.copy(SPRITE_FILE, opened_copy)
        sprite_before = bitmap_editor.canvas.animated_sprite

        bitmap_editor.load_opened_file(opened_copy)

        assert bitmap_editor.canvas.animated_sprite is not sprite_before
        assert bitmap_editor.canvas.animated_sprite.name == 'scarab'
