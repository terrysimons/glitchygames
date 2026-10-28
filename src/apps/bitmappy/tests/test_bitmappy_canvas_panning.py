#!/usr/bin/env python3
"""Tests for canvas panning (Ctrl+Shift+Arrow) and the canvas's single-frame save."""

from typing import TYPE_CHECKING

import pygame
import pytest

from bitmappy import SPRITE_CONFIG_DIR
from bitmappy.editor import AnimatedCanvasSprite, BitmapEditorScene
from bitmappy.history import CanvasPanCommand, OperationType
from bitmappy.panning import (
    MAX_PAN_DISTANCE,
    PanSession,
    can_pan_to,
    shift_pixels,
    transparent_pixel_for,
)
from glitchygames import events
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.testing.keys import qwerty_scancode

if TYPE_CHECKING:
    from pathlib import Path


class TestStaticSaveKeepsSpriteMetadata:
    """The canvas single-frame save keeps transitions, name, frame_anchor and hitbox."""

    def setup_method(self):
        """Create a canvas around a real 8x8 red one-frame sprite (each test replaces it)."""
        animated_sprite = AnimatedSprite()
        frame = SpriteFrame(pygame.Surface((8, 8)))
        frame.set_pixel_data([(255, 0, 0, 255)] * 64)
        animated_sprite.add_animation('test_animation', [frame])
        self.canvas = AnimatedCanvasSprite(
            animated_sprite=animated_sprite,
            pixels_across=8,
            pixels_tall=8,
            pixel_width=16,
            pixel_height=16,
        )

    def test_static_save_keeps_transitions(self, tmp_path):
        """The canvas's single-frame save path keeps the sprite's transitions."""
        import tomllib

        from glitchygames.sprites import AnimatedSprite

        sprite_file = tmp_path / 'single.toml'
        sprite_file.write_text(
            '[sprite]\nname = "single"\n\n'
            '[[animation]]\nnamespace = "idle"\nframe_interval = 0.15\n\n'
            '[[animation.frame]]\nnamespace = "idle"\nframe_index = 0\n'
            'pixels = """\n##\n##\n"""\n\n'
            '[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n\n'
            '[[transition]]\nfrom = "idle"\nto = "idle"\nwhen = "timer > 1.0"\n',
            encoding='utf-8',
        )
        self.canvas.animated_sprite = AnimatedSprite(str(sprite_file))
        saved_file = tmp_path / 'static.toml'

        self.canvas._save_as_static_sprite(str(saved_file), 'toml')

        saved_transitions = tomllib.loads(saved_file.read_text(encoding='utf-8'))['transition']
        assert saved_transitions == [{'from': 'idle', 'to': 'idle', 'when': 'timer > 1.0'}]

    def test_static_save_keeps_the_sprite_name(self, tmp_path):
        """battle_axe saved through the canvas's single-frame path keeps its name and glyphs."""
        import tomllib

        from glitchygames.sprites import AnimatedSprite

        source_file = SPRITE_CONFIG_DIR / 'battle_axe.toml'
        self.canvas.animated_sprite = AnimatedSprite(str(source_file))
        saved_file = tmp_path / 'battle_axe.toml'

        self.canvas._save_as_static_sprite(str(saved_file), 'toml')

        original_data = tomllib.loads(source_file.read_text(encoding='utf-8'))
        saved_data = tomllib.loads(saved_file.read_text(encoding='utf-8'))
        assert saved_data['sprite']['name'] == 'bttlaxe.get'
        assert saved_data['sprite']['pixels'] == original_data['sprite']['pixels']

    def test_static_save_keeps_frame_anchor_and_sprite_hitbox(self, tmp_path):
        """A sprite-level hitbox (not stored on the frame) and frame_anchor survive."""
        from glitchygames.sprites import AnimatedSprite, FrameAnchor

        sprite_file = tmp_path / 'anchored.toml'
        sprite_file.write_text(
            '[sprite]\nname = "anchored"\nframe_anchor = "bottom"\n\n'
            '[sprite.hitbox]\noffset_x = 0\noffset_y = 1\nwidth = 2\nheight = 1\n\n'
            '[[animation]]\nnamespace = "idle"\n\n'
            '[[animation.frame]]\nnamespace = "idle"\nframe_index = 0\n'
            'pixels = """\n..\n##\n"""\n\n'
            '[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n\n'
            '[colors."."]\nred = 255\ngreen = 0\nblue = 255\n',
            encoding='utf-8',
        )
        self.canvas.animated_sprite = AnimatedSprite(str(sprite_file))
        saved_file = tmp_path / 'static.toml'

        self.canvas._save_as_static_sprite(str(saved_file), 'toml')
        reloaded_sprite = AnimatedSprite(str(saved_file))

        assert reloaded_sprite.name == 'anchored'
        assert reloaded_sprite.frame_anchor is FrameAnchor.BOTTOM
        assert reloaded_sprite.default_hitbox == pygame.Rect(0, 1, 2, 1)


# ──────────────────────────────────────────────────────────────────────────────
# Panning in the real editor, driven by real key and mouse events
# ──────────────────────────────────────────────────────────────────────────────

MAGENTA_RGB = (255, 0, 255)
MAGENTA_RGBA = (255, 0, 255, 255)
RED_RGB = (255, 0, 0)
RED_RGBA = (255, 0, 0, 255)
GREEN_RGBA = (0, 255, 0, 255)
BLUE_RGB = (0, 0, 255)
BLUE_RGBA = (0, 0, 255, 255)
PAINT_RED = (200, 10, 10, 255)
PAINT_BLUE = (10, 10, 200, 255)
CONTROL_AND_SHIFT = pygame.KMOD_CTRL | pygame.KMOD_SHIFT


@pytest.fixture
def real_editor(mocker) -> BitmapEditorScene:
    """Build a real Bitmappy editor on the real display, with a fresh controller manager.

    The editor starts with one animation ('strip_1') of one blank 32x32 frame.

    Returns:
        The editor.

    """
    from bitmappy.controllers.manager import MultiControllerManager

    # The autouse conftest fixture already opened the real 800x600 display
    mocker.patch.object(MultiControllerManager, '_instance', None)
    return BitmapEditorScene(options={})


def press_key(editor: BitmapEditorScene, *, key: int, modifiers: int) -> None:
    """Send a real KEYDOWN event to the editor.

    Args:
        editor: The editor.
        key: The key pressed.
        modifiers: The modifier keys held (pygame.KMOD_* bits).

    """
    editor.on_key_down_event(
        events.HashableEvent(
            pygame.KEYDOWN,
            key=key,
            mod=modifiers,
            unicode='',
            scancode=qwerty_scancode(key=key),
        ),
    )


def release_key(editor: BitmapEditorScene, *, key: int, modifiers: int) -> None:
    """Send a real KEYUP event to the editor.

    Args:
        editor: The editor.
        key: The key released.
        modifiers: The modifier keys still held (pygame.KMOD_* bits).

    """
    editor.on_key_up_event(
        events.HashableEvent(
            pygame.KEYUP,
            key=key,
            mod=modifiers,
            unicode='',
            scancode=qwerty_scancode(key=key),
        ),
    )


def pan_once(editor: BitmapEditorScene, *, key: int) -> None:
    """Pan with Ctrl+Shift+<key>: press the arrow and release it, Ctrl and Shift held.

    Args:
        editor: The editor.
        key: The arrow key.

    """
    press_key(editor, key=key, modifiers=CONTROL_AND_SHIFT)
    release_key(editor, key=key, modifiers=CONTROL_AND_SHIFT)


def paint_pixel(
    editor: BitmapEditorScene,
    *,
    x: int,
    y: int,
    color: tuple[int, int, int, int],
) -> None:
    """Paint one canvas pixel with a real mouse click (press and release).

    Args:
        editor: The editor.
        x: The pixel's column.
        y: The pixel's row.
        color: The colour to paint.

    """
    canvas = editor.canvas
    canvas.active_color = color
    position = (
        canvas.rect.x + x * canvas.pixel_width + 1,
        canvas.rect.y + y * canvas.pixel_height + 1,
    )
    editor.on_left_mouse_button_down_event(
        events.HashableEvent(pygame.MOUSEBUTTONDOWN, pos=position, button=1),
    )
    editor.on_mouse_button_up_event(
        events.HashableEvent(pygame.MOUSEBUTTONUP, pos=position, button=1),
    )


def frame_pixels(editor: BitmapEditorScene) -> list[tuple[int, ...]]:
    """Return the pixel data of the frame the canvas shows.

    Args:
        editor: The editor.

    Returns:
        The frame's pixels, row by row.

    """
    canvas = editor.canvas
    frame = canvas.animated_sprite.animations[canvas.current_animation][canvas.current_frame]
    return frame.get_pixel_data()


def pixel_at(editor: BitmapEditorScene, *, x: int, y: int) -> tuple[int, ...]:
    """Return the frame pixel at a canvas position.

    Args:
        editor: The editor.
        x: The pixel's column.
        y: The pixel's row.

    Returns:
        The pixel's colour.

    """
    return frame_pixels(editor)[y * editor.canvas.pixels_across + x]


def drawn_color_at(editor: BitmapEditorScene, *, x: int, y: int) -> tuple[int, int, int, int]:
    """Return the colour the canvas draws for a pixel (the centre of its square).

    Args:
        editor: The editor.
        x: The pixel's column.
        y: The pixel's row.

    Returns:
        The drawn colour.

    """
    canvas = editor.canvas
    center = (
        x * canvas.pixel_width + canvas.pixel_width // 2,
        y * canvas.pixel_height + canvas.pixel_height // 2,
    )
    return tuple(canvas.image.get_at(center))  # ty: ignore[invalid-return-type]


def write_sprite_file(path: Path, *, opaque_glyph_color: str) -> Path:
    """Write a 2x2 one-animation ('idle') sprite with one dark pixel at the top left.

    Args:
        path: Where to write it.
        opaque_glyph_color: The TOML body of the dark pixel's colour table.

    Returns:
        The path.

    """
    path.write_text(
        '[sprite]\nname = "two_by_two"\n\n'
        '[[animation]]\nnamespace = "idle"\n\n'
        '[[animation.frame]]\nnamespace = "idle"\nframe_index = 0\n'
        'pixels = """\n#.\n..\n"""\n\n'
        f'[colors."#"]\n{opaque_glyph_color}\n\n'
        '[colors."."]\nred = 255\ngreen = 0\nblue = 255\n',
        encoding='utf-8',
    )
    return path


class TestPanningInTheRealEditor:
    """Ctrl+Shift+Arrow panning, driven through the real editor's key and mouse handlers."""

    def test_panning_shows_the_moved_pixels_while_the_arrow_is_held(self, real_editor):
        """The canvas draws the moved picture while Ctrl+Shift+Arrow is still held.

        The renderer drew the frame unless the canvas's _panning_active flag was set, and
        nothing set it, so the canvas kept drawing the unmoved picture until release.
        """
        paint_pixel(real_editor, x=0, y=0, color=PAINT_RED)

        press_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)
        real_editor.canvas.force_redraw()

        assert drawn_color_at(real_editor, x=1, y=0) == PAINT_RED
        assert drawn_color_at(real_editor, x=0, y=0) == MAGENTA_RGBA

    def test_releasing_control_before_the_arrow_still_keeps_the_pan(self, real_editor):
        """Letting go of Ctrl first, then the arrow, moves the frame as a normal release does.

        The release handler committed only when the arrow came up with Ctrl and Shift
        still held, so the frame kept the old picture while the canvas showed the new one.
        """
        paint_pixel(real_editor, x=0, y=0, color=PAINT_RED)

        press_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)
        release_key(real_editor, key=pygame.K_LCTRL, modifiers=pygame.KMOD_SHIFT)
        release_key(real_editor, key=pygame.K_RIGHT, modifiers=pygame.KMOD_SHIFT)

        assert pixel_at(real_editor, x=1, y=0) == PAINT_RED
        assert real_editor.canvas.pixels == frame_pixels(real_editor)

    def test_releasing_shift_before_the_arrow_still_keeps_the_pan(self, real_editor):
        """Letting go of Shift first, then the arrow, moves the frame too."""
        paint_pixel(real_editor, x=0, y=0, color=PAINT_RED)

        press_key(real_editor, key=pygame.K_DOWN, modifiers=CONTROL_AND_SHIFT)
        release_key(real_editor, key=pygame.K_LSHIFT, modifiers=pygame.KMOD_CTRL)
        release_key(real_editor, key=pygame.K_DOWN, modifiers=pygame.KMOD_CTRL)

        assert pixel_at(real_editor, x=0, y=1) == PAINT_RED
        assert real_editor.canvas.pixels == frame_pixels(real_editor)

    def test_paint_made_after_a_pan_survives_the_next_pan(self, real_editor):
        """A pixel painted between two pans moves with the second pan.

        Each pan shifted the pixels captured before the frame's first pan, so anything
        painted after it vanished on the next pan.
        """
        paint_pixel(real_editor, x=0, y=0, color=PAINT_RED)
        pan_once(real_editor, key=pygame.K_RIGHT)
        paint_pixel(real_editor, x=5, y=5, color=PAINT_BLUE)

        pan_once(real_editor, key=pygame.K_RIGHT)

        assert pixel_at(real_editor, x=2, y=0) == PAINT_RED
        assert pixel_at(real_editor, x=6, y=5) == PAINT_BLUE

    def test_loading_another_sprite_does_not_pan_the_old_sprites_pixels(
        self,
        real_editor,
        tmp_path,
    ):
        """Panning a newly loaded sprite moves its own pixels, not the previous sprite's.

        The panning state was keyed by animation name and frame index and was never
        cleared on load, so a sprite with the same names panned the old sprite's pixels.
        """
        first_sprite = write_sprite_file(
            tmp_path / 'first.toml',
            opaque_glyph_color='red = 0\ngreen = 0\nblue = 0',
        )
        second_sprite = write_sprite_file(
            tmp_path / 'second.toml',
            opaque_glyph_color='red = 0\ngreen = 200\nblue = 0',
        )
        real_editor.canvas.on_load_file_event(str(first_sprite))
        pan_once(real_editor, key=pygame.K_RIGHT)

        real_editor.canvas.on_load_file_event(str(second_sprite))
        press_key(real_editor, key=pygame.K_DOWN, modifiers=CONTROL_AND_SHIFT)

        assert real_editor.canvas.pixels == [
            MAGENTA_RGBA,
            MAGENTA_RGBA,
            (0, 200, 0, 255),
            MAGENTA_RGBA,
        ]

    def test_loading_a_sprite_ends_an_unfinished_pan(self, real_editor, tmp_path):
        """A pan gesture never finished before a load does not continue on the loaded sprite.

        Finishing it there would record an undo step that restores the old sprite's pixels.
        """
        sprite_path = write_sprite_file(
            tmp_path / 'loaded.toml',
            opaque_glyph_color='red = 0\ngreen = 0\nblue = 0',
        )
        press_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)

        real_editor.canvas.on_load_file_event(str(sprite_path))

        assert real_editor.canvas.pan_session is None

    def test_a_pan_is_undone_and_redone_as_one_step(self, real_editor):
        """Ctrl+Z after a pan restores the picture from before it; Ctrl+Shift+Z pans again."""
        paint_pixel(real_editor, x=0, y=0, color=PAINT_RED)
        pixels_before_the_pan = frame_pixels(real_editor)
        press_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)
        press_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)
        release_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)
        pixels_after_the_pan = frame_pixels(real_editor)
        release_key(real_editor, key=pygame.K_LSHIFT, modifiers=pygame.KMOD_CTRL)
        release_key(real_editor, key=pygame.K_LCTRL, modifiers=0)

        press_key(real_editor, key=pygame.K_z, modifiers=pygame.KMOD_CTRL)

        assert frame_pixels(real_editor) == pixels_before_the_pan
        assert real_editor.canvas.pixels == pixels_before_the_pan

        press_key(real_editor, key=pygame.K_z, modifiers=CONTROL_AND_SHIFT)

        assert frame_pixels(real_editor) == pixels_after_the_pan
        assert pixel_at(real_editor, x=2, y=0) == PAINT_RED
        assert real_editor.canvas.pixels == pixels_after_the_pan

    def test_panning_rgba_pixels_fills_with_rgba_magenta(self, real_editor, tmp_path):
        """Pixels uncovered by a pan of RGBA pixel data are RGBA magenta, not RGB magenta.

        The pan filled with (255, 0, 255) whatever the pixel data held, mixing RGB tuples
        into RGBA data.
        """
        sprite_path = write_sprite_file(
            tmp_path / 'translucent.toml',
            opaque_glyph_color='red = 0\ngreen = 0\nblue = 0\nalpha = 128',
        )
        real_editor.canvas.on_load_file_event(str(sprite_path))

        pan_once(real_editor, key=pygame.K_RIGHT)

        assert frame_pixels(real_editor) == [
            MAGENTA_RGBA,
            (0, 0, 0, 128),
            MAGENTA_RGBA,
            MAGENTA_RGBA,
        ]

    def test_panning_rgb_pixels_fills_with_rgb_magenta(self, real_editor):
        """Pixels uncovered by a pan of RGB pixel data stay RGB magenta."""
        pan_once(real_editor, key=pygame.K_RIGHT)

        assert all(pixel == MAGENTA_RGB for pixel in frame_pixels(real_editor))

    def test_a_pan_in_progress_does_not_carry_over_to_a_new_canvas(self, real_editor):
        """A new canvas starts with no pan gesture, even if one was never finished."""
        paint_pixel(real_editor, x=0, y=0, color=PAINT_RED)
        press_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)

        real_editor.on_new_file_event(dimensions='16x16')

        assert real_editor.canvas.pan_session is None


class TestPanningGesturesInTheRealEditor:
    """How a Ctrl+Shift+Arrow gesture starts, steps, ends and is undone, in the real editor."""

    def test_each_arrow_pans_its_own_way(self, real_editor):
        """Ctrl+Shift+Left, Right, Up and Down move the pixels left, right, up and down."""
        paint_pixel(real_editor, x=5, y=5, color=PAINT_RED)

        pan_once(real_editor, key=pygame.K_LEFT)
        assert pixel_at(real_editor, x=4, y=5) == PAINT_RED
        pan_once(real_editor, key=pygame.K_UP)
        assert pixel_at(real_editor, x=4, y=4) == PAINT_RED
        pan_once(real_editor, key=pygame.K_RIGHT)
        assert pixel_at(real_editor, x=5, y=4) == PAINT_RED
        pan_once(real_editor, key=pygame.K_DOWN)
        assert pixel_at(real_editor, x=5, y=5) == PAINT_RED

    def test_arrows_without_both_control_and_shift_do_not_pan(self, real_editor):
        """An arrow with only Ctrl, only Shift or neither leaves the pixels where they are."""
        paint_pixel(real_editor, x=5, y=5, color=PAINT_RED)

        for modifiers in (0, pygame.KMOD_CTRL, pygame.KMOD_SHIFT):
            press_key(real_editor, key=pygame.K_LEFT, modifiers=modifiers)
            release_key(real_editor, key=pygame.K_LEFT, modifiers=modifiers)

        assert pixel_at(real_editor, x=5, y=5) == PAINT_RED
        assert real_editor.canvas.pan_session is None

    def test_holding_the_arrow_pans_step_by_step_as_one_undo_step(self, real_editor):
        """Key repeats while the arrow is held each pan one more pixel; one undo undoes all."""
        paint_pixel(real_editor, x=0, y=0, color=PAINT_RED)
        pixels_before_the_pan = frame_pixels(real_editor)

        for _ in range(3):
            press_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)
        release_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)
        assert pixel_at(real_editor, x=3, y=0) == PAINT_RED

        real_editor.handle_undo()

        assert frame_pixels(real_editor) == pixels_before_the_pan

    def test_stepping_back_inside_one_pan_loses_nothing(self, real_editor):
        """Pixels pushed past the edge come back when the same pan moves them back."""
        paint_pixel(real_editor, x=31, y=0, color=PAINT_RED)

        press_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)
        assert PAINT_RED not in frame_pixels(real_editor)
        press_key(real_editor, key=pygame.K_LEFT, modifiers=CONTROL_AND_SHIFT)

        assert pixel_at(real_editor, x=31, y=0) == PAINT_RED

    def test_a_pan_that_ends_where_it_began_records_no_undo_step(self, real_editor):
        """Panning right then left in one gesture changes nothing, so nothing is undoable."""
        paint_pixel(real_editor, x=3, y=3, color=PAINT_RED)
        undo_steps_before = list(real_editor.undo_redo_manager.frame_undo_stacks['strip_1', 0])

        press_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)
        press_key(real_editor, key=pygame.K_LEFT, modifiers=CONTROL_AND_SHIFT)
        release_key(real_editor, key=pygame.K_LEFT, modifiers=CONTROL_AND_SHIFT)

        assert real_editor.undo_redo_manager.frame_undo_stacks['strip_1', 0] == undo_steps_before

    def test_a_pan_stops_ten_pixels_from_where_it_began(self, real_editor):
        """Steps past ten pixels from the gesture's start are ignored."""
        paint_pixel(real_editor, x=0, y=0, color=PAINT_RED)

        for _ in range(MAX_PAN_DISTANCE + 2):
            press_key(real_editor, key=pygame.K_DOWN, modifiers=CONTROL_AND_SHIFT)

        assert pixel_at(real_editor, x=0, y=MAX_PAN_DISTANCE) == PAINT_RED
        assert real_editor.canvas.pan_session is not None
        assert real_editor.canvas.pan_session.offset_y == MAX_PAN_DISTANCE

    def test_paint_made_during_a_pan_is_kept_and_undo_restores_the_start(self, real_editor):
        """A pixel painted while Ctrl+Shift+Arrow is held moves with the next step.

        Undoing the pan restores the frame from before the whole gesture.
        """
        pixels_before_the_pan = frame_pixels(real_editor)
        press_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)
        paint_pixel(real_editor, x=4, y=4, color=PAINT_BLUE)

        press_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)
        release_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)

        assert pixel_at(real_editor, x=5, y=4) == PAINT_BLUE
        real_editor.handle_undo()
        assert frame_pixels(real_editor) == pixels_before_the_pan

    def test_switching_frames_during_a_pan_records_the_first_frames_pan(
        self,
        real_editor,
        tmp_path,
    ):
        """A pan on frame 0, then a pan on frame 1 before any key came up, are two undo steps.

        Each frame's own undo restores its own pixels.
        """
        sprite_path = tmp_path / 'two_frames.toml'
        sprite_path.write_text(
            '[sprite]\nname = "two_frames"\n\n'
            '[[animation]]\nnamespace = "idle"\n\n'
            '[[animation.frame]]\nnamespace = "idle"\nframe_index = 0\n'
            'pixels = """\n#.\n..\n"""\n\n'
            '[[animation.frame]]\nnamespace = "idle"\nframe_index = 1\n'
            'pixels = """\n.#\n..\n"""\n\n'
            '[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n\n'
            '[colors."."]\nred = 255\ngreen = 0\nblue = 255\n',
            encoding='utf-8',
        )
        real_editor.canvas.on_load_file_event(str(sprite_path))
        first_frame_before = frame_pixels(real_editor)
        press_key(real_editor, key=pygame.K_DOWN, modifiers=CONTROL_AND_SHIFT)
        first_frame_panned = frame_pixels(real_editor)

        real_editor.canvas.show_frame('idle', 1)
        press_key(real_editor, key=pygame.K_DOWN, modifiers=CONTROL_AND_SHIFT)

        assert real_editor.undo_redo_manager.can_undo_frame('idle', 0) is True
        real_editor.canvas.show_frame('idle', 0)
        assert frame_pixels(real_editor) == first_frame_panned
        real_editor.handle_undo()
        assert frame_pixels(real_editor) == first_frame_before

    def test_releasing_another_key_does_not_end_the_pan(self, real_editor):
        """A key outside Ctrl+Shift+Arrow coming up leaves the gesture going."""
        press_key(real_editor, key=pygame.K_RIGHT, modifiers=CONTROL_AND_SHIFT)

        release_key(real_editor, key=pygame.K_a, modifiers=CONTROL_AND_SHIFT)

        assert real_editor.canvas.pan_session is not None

    def test_releasing_a_pan_key_with_no_pan_records_nothing(self, real_editor):
        """Letting go of Ctrl when nothing was panned adds no undo step."""
        undo_frames_before = dict(real_editor.undo_redo_manager.frame_undo_stacks)

        release_key(real_editor, key=pygame.K_RCTRL, modifiers=0)

        assert real_editor.undo_redo_manager.frame_undo_stacks == undo_frames_before

    def test_panning_and_finishing_without_a_canvas_do_nothing(self, real_editor):
        """With no canvas the pan handlers warn or return instead of failing."""
        real_editor.canvas = None

        real_editor._frame_operations.handle_canvas_panning(delta_x=1, delta_y=0)
        real_editor._frame_operations.finish_canvas_panning()
        release_key(real_editor, key=pygame.K_LEFT, modifiers=CONTROL_AND_SHIFT)


# ──────────────────────────────────────────────────────────────────────────────
# The canvas's own pan methods, on a real canvas around a real sprite
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def real_canvas() -> AnimatedCanvasSprite:
    """Build a real 3x2 canvas around a real two-frame sprite ('idle'), with no editor.

    Frame 0 is red, frame 1 is green; both are RGBA.

    Returns:
        The canvas.

    """
    # The autouse conftest fixture already opened the real 800x600 display
    frames = []
    for color in (RED_RGBA, GREEN_RGBA):
        frame = SpriteFrame(pygame.Surface((3, 2), pygame.SRCALPHA))
        frame.set_pixel_data([color] * 6)
        frames.append(frame)
    animated_sprite = AnimatedSprite()
    animated_sprite.add_animation('idle', frames)
    animated_sprite.set_animation('idle')
    return AnimatedCanvasSprite(
        animated_sprite=animated_sprite,
        pixels_across=3,
        pixels_tall=2,
        pixel_width=8,
        pixel_height=8,
    )


class TestCanvasPanMethods:
    """AnimatedCanvasSprite.pan_canvas, end_panning and replace_frame_pixels."""

    def test_pan_writes_the_moved_pixels_into_the_frame_and_the_canvas(self, real_canvas):
        """One step right moves the frame's pixels and the canvas's copy together."""
        real_canvas.pan_canvas(1, 0)

        expected_pixels = [MAGENTA_RGBA, RED_RGBA, RED_RGBA] * 2
        assert real_canvas.animated_sprite.animations['idle'][0].get_pixel_data() == (
            expected_pixels
        )
        assert real_canvas.pixels == expected_pixels
        assert real_canvas.pan_session is not None

    def test_panning_another_frame_starts_a_new_gesture_there(self, real_canvas):
        """A step on another frame starts from that frame's pixels."""
        real_canvas.pan_canvas(0, 1)
        real_canvas.show_frame('idle', 1)

        real_canvas.pan_canvas(0, -1)

        assert real_canvas.pan_session is not None
        assert real_canvas.pan_session.frame_index == 1
        assert real_canvas.pixels == [GREEN_RGBA] * 3 + [MAGENTA_RGBA] * 3

    def test_end_panning_returns_the_gesture_once(self, real_canvas):
        """Ending hands back the finished gesture, then there is none."""
        real_canvas.pan_canvas(1, 0)

        finished_session = real_canvas.end_panning()

        assert finished_session is not None
        assert finished_session.offset_x == 1
        assert finished_session.changed_the_frame is True
        assert real_canvas.end_panning() is None
        assert real_canvas.pan_session is None

    def test_pan_with_no_frame_shown_does_nothing(self, real_canvas):
        """With the canvas on an animation the sprite lacks, there is nothing to pan."""
        real_canvas.current_animation = 'missing'

        real_canvas.pan_canvas(1, 0)

        assert real_canvas.pan_session is None

    def test_replacing_pixels_of_a_missing_frame_is_refused(self, real_canvas, caplog):
        """A frame that does not exist is left alone, with a warning."""
        assert real_canvas.replace_frame_pixels(animation='idle', frame_index=5, pixels=[]) is False
        assert (
            real_canvas.replace_frame_pixels(animation='missing', frame_index=0, pixels=[]) is False
        )
        assert 'not found - pixels not replaced' in caplog.text

    def test_replacing_pixels_of_a_frame_not_shown_leaves_the_canvas(self, real_canvas):
        """Another frame's pixels change; the canvas keeps showing its own frame."""
        canvas_pixels_before = list(real_canvas.pixels)

        assert (
            real_canvas.replace_frame_pixels(
                animation='idle',
                frame_index=1,
                pixels=[BLUE_RGBA] * 6,
            )
            is True
        )

        assert real_canvas.animated_sprite.animations['idle'][1].get_pixel_data() == (
            [BLUE_RGBA] * 6
        )
        assert real_canvas.pixels == canvas_pixels_before


class TestCanvasPanCommand:
    """CanvasPanCommand when its canvas or frame is gone."""

    def test_undo_without_a_canvas_fails(self, mocker):
        """With no canvas there is nothing to restore, so undo reports failure."""
        editor = mocker.Mock(canvas=None, applying_undo_redo=False)
        pan_command = CanvasPanCommand(
            editor,
            animation='idle',
            frame=0,
            old_pixels=[RED_RGBA],
            new_pixels=[MAGENTA_RGBA],
        )

        assert pan_command.undo() is False
        assert pan_command.operation_type is OperationType.CANVAS_PAN
        assert pan_command.description == 'Pan idle[0]'

    def test_redo_on_a_deleted_frame_fails(self, real_canvas, mocker):
        """A pan of a frame that was deleted since cannot be redone."""
        editor = mocker.Mock(canvas=real_canvas, applying_undo_redo=False)
        pan_command = CanvasPanCommand(
            editor,
            animation='idle',
            frame=7,
            old_pixels=[RED_RGBA] * 6,
            new_pixels=[MAGENTA_RGBA] * 6,
        )

        assert pan_command.execute() is False


# ──────────────────────────────────────────────────────────────────────────────
# src/apps/bitmappy/src/bitmappy/panning.py
# ──────────────────────────────────────────────────────────────────────────────


# A 3x2 picture, row by row; each pixel is its own number so moves are easy to read
SIX_PIXEL_PICTURE = ((1,), (2,), (3,), (4,), (5,), (6,))


class TestShiftPixels:
    """shift_pixels moves row-by-row pixel data and fills what it uncovers."""

    def test_shift_right_drops_the_last_column(self):
        """Moving right fills the first column and drops the last."""
        assert shift_pixels(
            pixels=SIX_PIXEL_PICTURE, width=3, height=2, offset_x=1, offset_y=0
        ) == [
            MAGENTA_RGB,
            (1,),
            (2,),
            MAGENTA_RGB,
            (4,),
            (5,),
        ]

    def test_shift_up_and_left(self):
        """Moving up and left keeps only the bottom-right pixels, at the top left."""
        assert (
            shift_pixels(
                pixels=SIX_PIXEL_PICTURE,
                width=3,
                height=2,
                offset_x=-2,
                offset_y=-1,
            )
            == [(6,)] + [MAGENTA_RGB] * 5
        )

    def test_shift_past_the_picture_leaves_only_transparency(self):
        """Moving further than the picture is wide leaves nothing of it."""
        assert (
            shift_pixels(
                pixels=SIX_PIXEL_PICTURE,
                width=3,
                height=2,
                offset_x=3,
                offset_y=0,
            )
            == [MAGENTA_RGB] * 6
        )


class TestTransparentPixelFor:
    """transparent_pixel_for matches the pixel data's form."""

    def test_rgb_data_gets_rgb_magenta(self):
        """All-RGB pixel data is filled with RGB magenta."""
        assert transparent_pixel_for([RED_RGB, MAGENTA_RGB]) == MAGENTA_RGB

    def test_data_with_any_rgba_pixel_gets_rgba_magenta(self):
        """Pixel data holding an RGBA pixel (even mixed with RGB) is filled with RGBA magenta."""
        assert transparent_pixel_for([RED_RGB, RED_RGBA]) == MAGENTA_RGBA

    def test_empty_data_gets_rgb_magenta(self):
        """No pixels at all: RGB magenta (nothing says otherwise)."""
        assert transparent_pixel_for([]) == MAGENTA_RGB


class TestPanLimits:
    """can_pan_to allows up to MAX_PAN_DISTANCE on each axis, either way."""

    @pytest.mark.parametrize(
        ('offset_x', 'offset_y', 'allowed'),
        [
            (0, 0, True),
            (MAX_PAN_DISTANCE, -MAX_PAN_DISTANCE, True),
            (MAX_PAN_DISTANCE + 1, 0, False),
            (0, -MAX_PAN_DISTANCE - 1, False),
        ],
    )
    def test_limits(self, offset_x, offset_y, allowed):
        """Offsets within the limit are allowed; one more pixel on either axis is not."""
        assert can_pan_to(offset_x=offset_x, offset_y=offset_y) is allowed


class TestPanSession:
    """PanSession records one gesture."""

    def test_a_new_session_has_not_changed_the_frame(self):
        """A gesture that has not moved anything has nothing to undo."""
        session = PanSession.starting_from(animation='idle', frame_index=2, pixels=[RED_RGB])

        assert session.changed_the_frame is False
        assert session.is_for(animation='idle', frame_index=2) is True
        assert session.is_for(animation='idle', frame_index=1) is False
        assert session.is_for(animation='walk', frame_index=2) is False

    def test_rebasing_keeps_the_pixels_from_before_the_gesture(self):
        """After an edit the gesture moves the edited pixels; undo still has the first ones."""
        session = PanSession.starting_from(animation='idle', frame_index=0, pixels=[RED_RGB])
        moved_session = session.moved_to(offset_x=1, offset_y=0, panned_pixels=[MAGENTA_RGB])

        rebased_session = moved_session.rebased_on(pixels=[BLUE_RGB])

        assert rebased_session.pixels_before == (RED_RGB,)
        assert rebased_session.source_pixels == (BLUE_RGB,)
        assert (rebased_session.offset_x, rebased_session.offset_y) == (0, 0)
        assert rebased_session.panned_pixels == (BLUE_RGB,)
        assert rebased_session.changed_the_frame is True
