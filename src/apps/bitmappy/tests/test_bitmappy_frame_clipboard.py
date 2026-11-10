"""Bitmappy's frame clipboard, end to end: Ctrl+C and Ctrl+V on a real editor (BUGS.md #249).

The editor's copy and paste (``frame_operations.FrameOperationManager``) is the only one: a
second copy/paste in the film strip, the canvas and the coordinator, and the
``CrossAreaOperationTracker`` beside them, could never run and were removed. These tests drive
the one that remains the way a player does: a real ``BitmapEditorScene`` on the real display,
frames chosen through the film strip's selection handler, real key presses, and the editor's
own undo and redo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames import events
from glitchygames.testing.keys import qwerty_scancode

if TYPE_CHECKING:
    from pathlib import Path

    from bitmappy.editor import BitmapEditorScene

# Two animations of two 2x2 frames each, every frame different: '#' black, '.' magenta (the
# transparency key), 'o' white
SPRITE_TOML = """[sprite]
name = "clipboard"

[[animation]]
namespace = "idle"

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
#.
..
\"\"\"

[[animation.frame]]
namespace = "idle"
frame_index = 1
pixels = \"\"\"
.#
..
\"\"\"

[[animation]]
namespace = "walk"

[[animation.frame]]
namespace = "walk"
frame_index = 0
pixels = \"\"\"
oo
oo
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0

[colors."."]
red = 255
green = 0
blue = 255

[colors."o"]
red = 255
green = 255
blue = 255
"""


@pytest.fixture
def editor(bitmap_editor: BitmapEditorScene, tmp_path: Path) -> BitmapEditorScene:
    """Return a real editor with the two-animation sprite loaded, on idle frame 0.

    Returns:
        The editor.

    """
    sprite_path = tmp_path / 'clipboard.toml'
    sprite_path.write_text(SPRITE_TOML, encoding='utf-8')
    bitmap_editor.canvas.on_load_file_event(str(sprite_path))
    select_frame(bitmap_editor, animation='idle', frame=0)
    return bitmap_editor


def select_frame(editor: BitmapEditorScene, *, animation: str, frame: int) -> None:
    """Choose a frame as a click on its film strip does (the editor's selection and canvas).

    Args:
        editor: The editor.
        animation: The animation.
        frame: The frame's index.

    """
    editor.on_film_strip_frame_selected(editor.film_strips[animation], animation, frame)


def press_control(editor: BitmapEditorScene, *, key: int) -> None:
    """Press Ctrl and a key, as a real KEYDOWN event reaches the editor.

    Args:
        editor: The editor.
        key: The key pressed with Ctrl.

    """
    editor.on_key_down_event(
        events.HashableEvent(
            pygame.KEYDOWN,
            key=key,
            mod=pygame.KMOD_CTRL,
            unicode='',
            scancode=qwerty_scancode(key=key),
        )
    )


def frame_pixels(editor: BitmapEditorScene, *, animation: str, frame: int) -> list[tuple[int, ...]]:
    """Return a frame's pixels, as the sprite holds them.

    Returns:
        The pixels, row by row.

    """
    return editor.canvas.animated_sprite.animations[animation][frame].get_pixel_data()


class TestTheFrameClipboard:
    """Ctrl+C copies the selected frame; Ctrl+V pastes it onto the selected frame, undoably."""

    def test_ctrl_c_then_ctrl_v_puts_one_frame_onto_another(self, editor):
        """Frame 0 copied and pasted onto frame 1: frame 1 holds frame 0's pixels."""
        copied = frame_pixels(editor, animation='idle', frame=0)
        assert frame_pixels(editor, animation='idle', frame=1) != copied

        press_control(editor, key=pygame.K_c)
        select_frame(editor, animation='idle', frame=1)
        press_control(editor, key=pygame.K_v)

        assert frame_pixels(editor, animation='idle', frame=1) == copied
        assert frame_pixels(editor, animation='idle', frame=0) == copied

    def test_a_paste_is_one_undo_step_and_redoes(self, editor):
        """Undo restores the frame the paste replaced; redo pastes it again."""
        copied = frame_pixels(editor, animation='idle', frame=0)
        before_the_paste = frame_pixels(editor, animation='idle', frame=1)
        press_control(editor, key=pygame.K_c)
        select_frame(editor, animation='idle', frame=1)
        press_control(editor, key=pygame.K_v)

        press_control(editor, key=pygame.K_z)
        assert frame_pixels(editor, animation='idle', frame=1) == before_the_paste

        press_control(editor, key=pygame.K_y)
        assert frame_pixels(editor, animation='idle', frame=1) == copied

    def test_a_frame_pastes_into_another_animation(self, editor):
        """One clipboard for the whole sprite: walk's frame pasted onto an idle frame."""
        select_frame(editor, animation='walk', frame=0)
        copied = frame_pixels(editor, animation='walk', frame=0)
        press_control(editor, key=pygame.K_c)

        select_frame(editor, animation='idle', frame=1)
        press_control(editor, key=pygame.K_v)

        assert frame_pixels(editor, animation='idle', frame=1) == copied

    def test_a_paste_with_nothing_copied_changes_nothing(self, editor):
        """Ctrl+V before any Ctrl+C leaves the frame as it is and records no undo step."""
        before = frame_pixels(editor, animation='idle', frame=1)
        select_frame(editor, animation='idle', frame=1)

        press_control(editor, key=pygame.K_v)

        assert frame_pixels(editor, animation='idle', frame=1) == before
        assert not editor.undo_redo_manager.can_undo_frame('idle', 1)

    def test_the_clipboard_keeps_its_frame_after_the_source_changes(self, editor):
        """The copy is a snapshot: repainting the source does not change what pastes."""
        copied = frame_pixels(editor, animation='idle', frame=0)
        press_control(editor, key=pygame.K_c)
        repainted = [(255, 255, 255)] * len(copied)
        editor.canvas.animated_sprite.animations['idle'][0].set_pixel_data(repainted)

        select_frame(editor, animation='idle', frame=1)
        press_control(editor, key=pygame.K_v)

        assert frame_pixels(editor, animation='idle', frame=1) == copied
