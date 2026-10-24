"""A failed Bitmappy save is reported in the editor, which keeps running (BUGS.md #214)."""

from __future__ import annotations

import pygame

from glitchygames.events.base import HashableEvent
from glitchygames.ui.dialogs import SaveDialogScene


def test_a_save_into_a_missing_folder_shows_the_error_and_keeps_the_drawing(
    bitmap_editor, tmp_path
):
    """The canvas's OSError reaches the Save dialog, which shows it in the editor's text box."""
    sprite_before = bitmap_editor.canvas.animated_sprite
    dialog = SaveDialogScene(previous_scene=bitmap_editor, groups=pygame.sprite.LayeredDirty())
    dialog.dialog.input_box.text = str(tmp_path / 'missing folder' / 'sprite.toml')
    confirm = HashableEvent(pygame.MOUSEBUTTONUP, pos=(0, 0), button=1)

    dialog.on_confirm_event(confirm, dialog.dialog.confirm_button)

    assert bitmap_editor.next_scene is bitmap_editor
    assert bitmap_editor.canvas.animated_sprite is sprite_before
    assert bitmap_editor.debug_text.text.startswith('Error saving')
    assert 'sprite.toml' in bitmap_editor.debug_text.text
    assert not (tmp_path / 'missing folder').exists()
