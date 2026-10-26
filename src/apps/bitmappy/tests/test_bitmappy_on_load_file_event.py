"""Test suite for on_load_file_event functionality.

This module tests the file loading functionality of the bitmappy editor's canvas, specifically
the on_load_file_event method that loads animated sprites from files. Every test loads a real
sprite file into a real editor scene (real canvas, real film strips, the real display).
"""

import logging
from typing import TYPE_CHECKING

import pygame
import pytest

from bitmappy.controllers.manager import MultiControllerManager
from bitmappy.editor import BitmapEditorScene
from glitchygames.events import HashableEvent
from glitchygames.sprites import AnimatedSprite

if TYPE_CHECKING:
    from pathlib import Path

    from bitmappy.animated_canvas import AnimatedCanvasSprite

RED = (255, 0, 0)
GREEN = (0, 255, 0)

# An 8x8 frame: a red border around a green square ('0' is red, '1' is green)
BORDERED_FRAME_ROWS = (
    '00000000',
    '01111110',
    '01111110',
    '01111110',
    '01111110',
    '01111110',
    '01111110',
    '00000000',
)
# An 8x8 frame filled with red
SOLID_RED_FRAME_ROWS = ('00000000',) * 8
# A 10x10 frame: a red border around a green square
TEN_BY_TEN_FRAME_ROWS = ('0000000000', *(('0111111110',) * 8), '0000000000')


def sprite_file_content(
    *, sprite_name: str, animations: dict[str, list[tuple[str, ...]]], description: str = ''
) -> str:
    """Build the TOML text of an animated sprite with red ('0') and green ('1') pixels.

    Args:
        sprite_name: The sprite's name.
        animations: Each animation's frames, in file order, as rows of pixel characters.
        description: The sprite's description (omitted when empty).

    Returns:
        The TOML text.

    """
    lines = ['[sprite]', f'name = "{sprite_name}"']
    if description:
        lines.append(f'description = "{description}"')
    lines += [
        '',
        '[colors.0]',
        'red = 255',
        'green = 0',
        'blue = 0',
        '',
        '[colors.1]',
        'red = 0',
        'green = 255',
        'blue = 0',
    ]
    for animation_name, frames in animations.items():
        lines += [
            '',
            '[[animation]]',
            f'namespace = "{animation_name}"',
            'frame_interval = 0.5',
            'loop = true',
        ]
        for frame_index, rows in enumerate(frames):
            lines += [
                '',
                '[[animation.frame]]',
                f'namespace = "{animation_name}"',
                f'frame_index = {frame_index}',
                'pixels = """',
                *rows,
                '"""',
            ]
    return '\n'.join(lines) + '\n'


def expected_pixel_colors(rows: tuple[str, ...]) -> list[tuple[int, int, int]]:
    """Return the RGB color of each pixel of a frame, row by row.

    Args:
        rows: The frame's rows of pixel characters ('0' red, '1' green).

    Returns:
        The colors, in canvas pixel order.

    """
    return [RED if character == '0' else GREEN for row in rows for character in row]


def canvas_pixel_colors(canvas: AnimatedCanvasSprite) -> list[tuple[int, int, int]]:
    """Return the RGB part of each canvas pixel (the canvas may hold RGBA pixels).

    Args:
        canvas: The canvas.

    Returns:
        The colors, in canvas pixel order.

    """
    return [tuple(pixel[:3]) for pixel in canvas.pixels]  # type: ignore[misc]


def load_file_event(*, filename: str) -> HashableEvent:
    """Make the load-file event the editor sends: an event whose text is the file name.

    Args:
        filename: The file to load.

    Returns:
        The event.

    """
    return HashableEvent(pygame.USEREVENT, text=filename)


class TestOnLoadFileEvent:
    """Test suite for on_load_file_event functionality."""

    @pytest.fixture(autouse=True)
    def editor_scene(self, mocker):
        """Create a real editor scene with its real canvas.

        Returns:
            BitmapEditorScene: The editor scene.

        """
        # A fresh controller manager for this editor (it is a singleton)
        mocker.patch.object(MultiControllerManager, '_instance', None)
        self.scene = BitmapEditorScene(options={})
        self.canvas = self.scene.canvas
        return self.scene

    @staticmethod
    def _write_sprite_file(*, directory: Path, file_name: str, content: str) -> str:
        """Write a sprite file.

        Args:
            directory: The directory to write it in.
            file_name: The file's name.
            content: The file's text.

        Returns:
            str: The file's path.

        """
        path = directory / file_name
        path.write_text(content, encoding='utf-8')
        return str(path)

    @staticmethod
    def _get_first_animation_name(sprite: AnimatedSprite) -> str:
        """Get the first animation name from a sprite.

        This follows the same logic as _set_initial_animation:
        1. First try to find "idle" animation
        2. If no "idle" animation exists, use the first animation in file order
        3. If no animation order is available, fall back to the first key in _animations

        Returns:
            str: The first animation name.

        """
        if not hasattr(sprite, '_animations') or not sprite._animations:
            return ''

        # First try to find "idle" animation
        if 'idle' in sprite._animations:
            return 'idle'

        # Use the first animation as it appears in the file order
        if hasattr(sprite, '_animation_order') and sprite._animation_order:
            return sprite._animation_order[0]

        # Fall back to the first key in _animations
        return next(iter(sprite._animations.keys()))

    def test_load_valid_animated_sprite(self, tmp_path):
        """Loading a two-frame sprite makes it the canvas's sprite and shows its first frame."""
        sprite_file = self._write_sprite_file(
            directory=tmp_path,
            file_name='test_sprite.toml',
            content=sprite_file_content(
                sprite_name='test_sprite',
                animations={'idle': [BORDERED_FRAME_ROWS, SOLID_RED_FRAME_ROWS]},
            ),
        )
        sprite_before = self.canvas.animated_sprite

        self.canvas.on_load_file_event(load_file_event(filename=sprite_file))

        loaded_sprite = self.canvas.animated_sprite
        assert loaded_sprite is not sprite_before
        assert isinstance(loaded_sprite, AnimatedSprite)
        assert loaded_sprite.name == 'test_sprite'
        assert list(loaded_sprite._animations) == ['idle']
        assert len(loaded_sprite._animations['idle']) == 2
        assert (self.canvas.pixels_across, self.canvas.pixels_tall) == (8, 8)
        assert canvas_pixel_colors(self.canvas) == expected_pixel_colors(BORDERED_FRAME_ROWS)

    def test_load_file_not_found(self, tmp_path, caplog):
        """A missing file is logged and reported in the editor; the canvas keeps its sprite."""
        missing_file = str(tmp_path / 'nonexistent.toml')
        sprite_before = self.canvas.animated_sprite
        pixels_before = list(self.canvas.pixels)

        with caplog.at_level(logging.ERROR):
            # Should handle the exception gracefully (no raise)
            self.canvas.on_load_file_event(load_file_event(filename=missing_file))

        assert any('File not found' in record.getMessage() for record in caplog.records)
        assert self.scene.debug_text.text.startswith('Error: File not found')
        assert self.canvas.animated_sprite is sprite_before
        assert self.canvas.pixels == pixels_before

    def test_load_invalid_file_format(self, tmp_path, caplog):
        """A file that is not a sprite is logged and reported; the canvas keeps its sprite."""
        invalid_file = self._write_sprite_file(
            directory=tmp_path, file_name='invalid.txt', content='this is not a sprite\n'
        )
        sprite_before = self.canvas.animated_sprite

        with caplog.at_level(logging.ERROR):
            self.canvas.on_load_file_event(load_file_event(filename=invalid_file))

        error_messages = [record.getMessage() for record in caplog.records]
        assert any(
            'Error in on_load_file_event for animated sprite' in message
            for message in error_messages
        )
        assert self.scene.debug_text.text.startswith('Error loading sprite')
        assert self.canvas.animated_sprite is sprite_before

    def test_canvas_resize_on_different_dimensions(self, tmp_path):
        """A 10x10 sprite resizes the 32x32 canvas to 10x10 and fills it with the frame."""
        sprite_file = self._write_sprite_file(
            directory=tmp_path,
            file_name='ten_by_ten.toml',
            content=sprite_file_content(
                sprite_name='ten_by_ten', animations={'idle': [TEN_BY_TEN_FRAME_ROWS]}
            ),
        )
        assert (self.canvas.pixels_across, self.canvas.pixels_tall) == (32, 32)

        self.canvas.on_load_file_event(load_file_event(filename=sprite_file))

        assert (self.canvas.pixels_across, self.canvas.pixels_tall) == (10, 10)
        assert len(self.canvas.pixels) == 100
        assert canvas_pixel_colors(self.canvas) == expected_pixel_colors(TEN_BY_TEN_FRAME_ROWS)

    def test_ui_components_update_after_load(self, tmp_path):
        """The film strips are rebuilt for the loaded animations and the prompt is updated."""
        sprite_file = self._write_sprite_file(
            directory=tmp_path,
            file_name='two_animations.toml',
            content=sprite_file_content(
                sprite_name='test_sprite_ui',
                animations={
                    'test_sprite_ui': [BORDERED_FRAME_ROWS],
                    'other': [SOLID_RED_FRAME_ROWS],
                },
                description='A bordered square',
            ),
        )

        self.canvas.on_load_file_event(load_file_event(filename=sprite_file))

        loaded_sprite = self.canvas.animated_sprite
        assert set(self.scene.film_strips) == set(loaded_sprite._animations)
        assert set(self.scene.film_strip_sprites) == set(loaded_sprite._animations)
        # Each strip shows one animation of the loaded sprite: the same frame objects
        for animation_name, film_strip in self.scene.film_strips.items():
            assert list(film_strip.animated_sprite._animations) == [animation_name]
            assert (
                film_strip.animated_sprite._animations[animation_name]
                == loaded_sprite._animations[animation_name]
            )
        # The sprite's description replaces the AI prompt
        assert self.scene.debug_text.text == 'A bordered square'

    def test_animation_state_after_load(self, tmp_path):
        """Without an "idle" animation, the first animation in the file is current and playing."""
        sprite_file = self._write_sprite_file(
            directory=tmp_path,
            file_name='walk_and_run.toml',
            content=sprite_file_content(
                sprite_name='test_sprite',
                animations={
                    'walk': [BORDERED_FRAME_ROWS, SOLID_RED_FRAME_ROWS],
                    'run': [SOLID_RED_FRAME_ROWS],
                },
            ),
        )

        self.canvas.on_load_file_event(load_file_event(filename=sprite_file))

        loaded_sprite = self.canvas.animated_sprite
        expected_animation = self._get_first_animation_name(loaded_sprite)
        assert expected_animation == 'walk'
        assert self.canvas.current_animation == expected_animation
        assert loaded_sprite.current_animation == expected_animation
        assert loaded_sprite.is_playing
        assert loaded_sprite._is_looping
        # Without a description the AI prompt is the default one
        assert self.scene.debug_text.text == (
            'Enter a description of the sprite you want to create:'
        )

    def test_string_event_parameter(self, tmp_path):
        """The method also takes the file name as a plain string instead of an event."""
        sprite_file = self._write_sprite_file(
            directory=tmp_path,
            file_name='test_sprite.toml',
            content=sprite_file_content(
                sprite_name='test_sprite', animations={'idle': [BORDERED_FRAME_ROWS]}
            ),
        )

        self.canvas.on_load_file_event(sprite_file)  # type: ignore[invalid-argument-type]

        assert self.canvas.animated_sprite.name == 'test_sprite'
        assert canvas_pixel_colors(self.canvas) == expected_pixel_colors(BORDERED_FRAME_ROWS)

    def test_load_into_a_canvas_without_a_parent_scene_or_callback(self, tmp_path, caplog):
        """A canvas with no parent scene and no on_sprite_loaded callback still loads the sprite."""
        sprite_file = self._write_sprite_file(
            directory=tmp_path,
            file_name='orphan.toml',
            content=sprite_file_content(
                sprite_name='orphan', animations={'idle': [BORDERED_FRAME_ROWS]}
            ),
        )
        # Undo the editor's wiring: no parent scene, no on_sprite_loaded callback
        self.canvas.parent_scene = None
        del self.canvas.on_sprite_loaded
        film_strips_before = dict(self.scene.film_strips)

        # Name the canvas's logger: another test may have raised its level
        with caplog.at_level(logging.DEBUG, logger=self.canvas.log.name):
            self.canvas.on_load_file_event(load_file_event(filename=sprite_file))

        assert self.canvas.animated_sprite.name == 'orphan'
        assert canvas_pixel_colors(self.canvas) == expected_pixel_colors(BORDERED_FRAME_ROWS)
        assert any(
            'No parent scene or callback found' in record.getMessage() for record in caplog.records
        )
        # Nobody was told: the editor's film strips were not rebuilt
        assert self.scene.film_strips == film_strips_before


class TestEditorCanvasSize:
    """The editor's canvas size option."""

    def test_size_option_sets_the_canvas_size(self, mocker):
        """A 'size' option is kept (not replaced by the 32x32 default) and sizes the canvas."""
        # A fresh controller manager for this editor (it is a singleton)
        mocker.patch.object(MultiControllerManager, '_instance', None)
        options = {'size': '16x8'}

        scene = BitmapEditorScene(options=options)

        assert options['size'] == '16x8'
        assert (scene.canvas.pixels_across, scene.canvas.pixels_tall) == (16, 8)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
