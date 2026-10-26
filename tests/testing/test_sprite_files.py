"""The sprite-file checks (glitchygames/testing/sprite_files.py): good sprites pass, bad ones fail.

Each ``check_*`` runs on a good synthetic sprite written to ``tmp_path`` (it passes) and on a bad
one (it raises ``AssertionError`` naming the sprite file). A save that loses data is injected by
patching ``AnimatedSprite.save`` to write an altered file, since the real writer keeps everything.
"""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

from glitchygames.display_mode import set_display_mode
from glitchygames.sprites import AnimatedSprite
from glitchygames.testing import sprite_files

DISPLAY_SIZE = (96, 64)

COLORS_SECTION = (
    '[colors."#"]\nred = 90\ngreen = 90\nblue = 90\n\n'
    '[colors."."]\nred = 255\ngreen = 0\nblue = 255\n'
)

STATIC_SPRITE = (
    '[sprite]\nname = "rock"\ndescription = """A grey rock."""\nframe_anchor = "bottom"\n'
    'pixels = """\n#.\n##\n"""\n\n'
    '[sprite.hitbox]\noffset_x = 0\noffset_y = 0\nwidth = 2\nheight = 2\n\n'
    f'{COLORS_SECTION}'
)

STATIC_SPRITE_WITHOUT_HITBOX = (
    f'[sprite]\nname = "rock"\npixels = """\n#.\n##\n"""\n\n{COLORS_SECTION}'
)

ANIMATED_SPRITE = (
    '[sprite]\nname = "walker"\n\n'
    '[[animation]]\nnamespace = "walk"\nframe_interval = 0.1\nloop = true\n\n'
    '[[animation.frame]]\nnamespace = "walk"\nframe_index = 0\nframe_interval = 0.25\n'
    'pixels = """\n#.\n##\n"""\n\n'
    '[[animation.frame]]\nnamespace = "walk"\nframe_index = 1\nframe_interval = 0.75\n'
    'pixels = """\n.#\n##\n"""\n\n'
    '[[transition]]\nfrom = "walk"\nto = "walk"\n\n'
    f'{COLORS_SECTION}'
)

ONE_FRAME_ANIMATED_SPRITE = (
    '[sprite]\nname = "blinker"\n\n'
    '[[animation]]\nnamespace = "blink"\nframe_interval = 0.1\nloop = true\n\n'
    '[[animation.frame]]\nnamespace = "blink"\nframe_index = 0\nframe_interval = 0.25\n'
    'pixels = """\n#.\n##\n"""\n\n'
    f'{COLORS_SECTION}'
)

UNEVEN_ROWS_SPRITE = f'[sprite]\nname = "ragged"\npixels = """\n#.\n###\n"""\n\n{COLORS_SECTION}'

UNEVEN_FRAME_ROWS_SPRITE = (
    '[sprite]\nname = "ragged"\n\n'
    '[[animation]]\nnamespace = "walk"\n\n'
    '[[animation.frame]]\nnamespace = "walk"\nframe_index = 0\npixels = """\n#.\n###\n"""\n\n'
    '[[animation.frame]]\nnamespace = "walk"\nframe_index = 1\nframe_interval = 0.5\n\n'
    f'{COLORS_SECTION}'
)


@pytest.fixture(autouse=True)
def real_display() -> None:
    """Give AnimatedSprite a real display for loading and saving."""
    pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=DISPLAY_SIZE)


def write_sprite(*, directory: Path, name: str, text: str) -> Path:
    """Write a sprite file.

    Returns:
        Path: The file written.

    """
    sprite_file = directory / name
    sprite_file.write_text(text, encoding='utf-8')
    return sprite_file


def save_altered(*, mocker, find: str, replace: str) -> None:
    """Make ``AnimatedSprite.save`` write the sprite's source with ``find`` replaced.

    The real writer keeps everything, so a lossy save is injected: the saved file is the
    original text altered the way a lossy writer would alter it.
    """
    original_text_by_name: dict[str, str] = {}
    real_init = AnimatedSprite.__init__

    def remembering_init(self, filename: str = '', *args, **kwargs) -> None:
        real_init(self, filename, *args, **kwargs)
        if filename:
            original_text_by_name[filename] = Path(filename).read_text(encoding='utf-8')
            self.remembered_source = filename

    def altered_save(self, filename: str, file_format: str = 'toml') -> None:
        del file_format
        text = original_text_by_name[self.remembered_source]
        Path(filename).write_text(text.replace(find, replace), encoding='utf-8')

    mocker.patch.object(AnimatedSprite, '__init__', remembering_init)
    mocker.patch.object(AnimatedSprite, 'save', altered_save)


class TestRowsHaveEqualLengths:
    """check_rows_have_equal_lengths."""

    def test_even_rows_pass(self, tmp_path):
        """A sprite whose rows are one width passes."""
        sprite_file = write_sprite(directory=tmp_path, name='good.toml', text=STATIC_SPRITE)
        sprite_files.check_rows_have_equal_lengths(sprite_file=sprite_file)

    def test_a_sprite_without_pixels_passes(self, tmp_path):
        """A file with no pixel block has no rows to compare."""
        sprite_file = write_sprite(
            directory=tmp_path, name='empty.toml', text='[sprite]\nname = "none"\n'
        )
        sprite_files.check_rows_have_equal_lengths(sprite_file=sprite_file)

    def test_uneven_static_rows_fail_naming_the_file(self, tmp_path):
        """A static sprite with a long row fails, naming the file, block and lengths."""
        sprite_file = write_sprite(directory=tmp_path, name='bad.toml', text=UNEVEN_ROWS_SPRITE)
        with pytest.raises(AssertionError, match=r'bad\.toml sprite: row lengths \[2, 3\]'):
            sprite_files.check_rows_have_equal_lengths(sprite_file=sprite_file)

    def test_uneven_animation_frame_rows_fail_naming_the_frame(self, tmp_path):
        """A frame with uneven rows fails, naming the animation and frame."""
        sprite_file = write_sprite(
            directory=tmp_path, name='bad_frame.toml', text=UNEVEN_FRAME_ROWS_SPRITE
        )
        with pytest.raises(AssertionError, match=r'animation 0 frame 0: row lengths \[2, 3\]'):
            sprite_files.check_rows_have_equal_lengths(sprite_file=sprite_file)


class TestAnimationTimings:
    """check_animation_timings_survive_a_save_round_trip."""

    def test_a_faithful_save_passes(self, tmp_path):
        """Timings written back as read pass."""
        sprite_file = write_sprite(directory=tmp_path, name='walker.toml', text=ANIMATED_SPRITE)
        saved_directory = tmp_path / 'saved'
        saved_directory.mkdir()
        sprite_files.check_animation_timings_survive_a_save_round_trip(
            sprite_file=sprite_file, directory=saved_directory
        )

    def test_a_single_frame_sprite_is_skipped(self, tmp_path):
        """A one-frame sprite is saved in the static format, without timing: skipped."""
        sprite_file = write_sprite(directory=tmp_path, name='rock.toml', text=STATIC_SPRITE)
        with pytest.raises(pytest.skip.Exception, match='without timing'):
            sprite_files.check_animation_timings_survive_a_save_round_trip(
                sprite_file=sprite_file, directory=tmp_path
            )

    def test_a_lost_frame_interval_fails(self, tmp_path, mocker):
        """A writer that hard-codes frame_interval = 0.5 fails the comparison."""
        sprite_file = write_sprite(directory=tmp_path, name='walker.toml', text=ANIMATED_SPRITE)
        save_altered(mocker=mocker, find='frame_interval = 0.1', replace='frame_interval = 0.5')
        saved_directory = tmp_path / 'saved'
        saved_directory.mkdir()
        with pytest.raises(AssertionError, match=r'walker\.toml'):
            sprite_files.check_animation_timings_survive_a_save_round_trip(
                sprite_file=sprite_file, directory=saved_directory
            )

    def test_a_reloaded_duration_that_differs_fails(self, tmp_path, mocker):
        """A save whose per-frame durations reload differently fails, naming the animation."""
        sprite_file = write_sprite(directory=tmp_path, name='walker.toml', text=ANIMATED_SPRITE)
        saved_directory = tmp_path / 'saved'
        saved_directory.mkdir()
        mocker.patch.object(
            sprite_files, '_animation_timings', return_value=[('walk', 0.1, True, [None])]
        )
        save_altered(mocker=mocker, find='frame_interval = 0.75', replace='frame_interval = 0.5')
        with pytest.raises(AssertionError, match=r'walk'):
            sprite_files.check_animation_timings_survive_a_save_round_trip(
                sprite_file=sprite_file, directory=saved_directory
            )


class TestHitboxes:
    """check_hitboxes_survive_a_save_round_trip_unchanged."""

    def test_a_faithful_save_passes(self, tmp_path):
        """A sprite with a hitbox, and one without, keep exactly what they defined."""
        for name, text in (('a.toml', STATIC_SPRITE), ('b.toml', STATIC_SPRITE_WITHOUT_HITBOX)):
            sprite_file = write_sprite(directory=tmp_path, name=name, text=text)
            saved_directory = tmp_path / f'saved_{name}'
            saved_directory.mkdir()
            sprite_files.check_hitboxes_survive_a_save_round_trip_unchanged(
                sprite_file=sprite_file, directory=saved_directory
            )

    def test_an_animated_sprite_passes(self, tmp_path):
        """An animated sprite's frame hitboxes (none defined) stay none."""
        sprite_file = write_sprite(directory=tmp_path, name='walker.toml', text=ANIMATED_SPRITE)
        saved_directory = tmp_path / 'saved'
        saved_directory.mkdir()
        sprite_files.check_hitboxes_survive_a_save_round_trip_unchanged(
            sprite_file=sprite_file, directory=saved_directory
        )

    def test_a_one_frame_animation_is_skipped(self, tmp_path):
        """A one-frame animation is saved in the static format: skipped."""
        sprite_file = write_sprite(
            directory=tmp_path, name='blinker.toml', text=ONE_FRAME_ANIMATED_SPRITE
        )
        with pytest.raises(pytest.skip.Exception, match='static format'):
            sprite_files.check_hitboxes_survive_a_save_round_trip_unchanged(
                sprite_file=sprite_file, directory=tmp_path
            )

    def test_a_synthesised_hitbox_fails(self, tmp_path, mocker):
        """A writer that adds a hitbox the file never defined fails."""
        sprite_file = write_sprite(
            directory=tmp_path, name='rock.toml', text=STATIC_SPRITE_WITHOUT_HITBOX
        )
        save_altered(
            mocker=mocker,
            find='[colors."#"]',
            replace='[sprite.hitbox]\noffset_x = 0\noffset_y = 0\nwidth = 2\nheight = 2\n\n'
            '[colors."#"]',
        )
        saved_directory = tmp_path / 'saved'
        saved_directory.mkdir()
        with pytest.raises(AssertionError, match=r'rock\.toml'):
            sprite_files.check_hitboxes_survive_a_save_round_trip_unchanged(
                sprite_file=sprite_file, directory=saved_directory
            )


class TestPixels:
    """check_pixels_survive_a_save_round_trip."""

    def test_a_faithful_save_passes(self, tmp_path):
        """Pixels written and reloaded are the same."""
        sprite_file = write_sprite(directory=tmp_path, name='walker.toml', text=ANIMATED_SPRITE)
        saved_directory = tmp_path / 'saved'
        saved_directory.mkdir()
        sprite_files.check_pixels_survive_a_save_round_trip(
            sprite_file=sprite_file, directory=saved_directory
        )

    def test_a_changed_pixel_fails_naming_the_frame(self, tmp_path, mocker):
        """A save that flips a pixel fails, naming the file and the frame."""
        sprite_file = write_sprite(directory=tmp_path, name='rock.toml', text=STATIC_SPRITE)
        save_altered(mocker=mocker, find='#.\n##', replace='..\n##')
        saved_directory = tmp_path / 'saved'
        saved_directory.mkdir()
        with pytest.raises(AssertionError, match=r'rock\.toml.*frame'):
            sprite_files.check_pixels_survive_a_save_round_trip(
                sprite_file=sprite_file, directory=saved_directory
            )

    def test_a_lost_frame_fails(self, tmp_path, mocker):
        """A save that drops a frame fails on the frame count."""
        sprite_file = write_sprite(directory=tmp_path, name='walker.toml', text=ANIMATED_SPRITE)
        save_altered(
            mocker=mocker,
            find='[[animation.frame]]\nnamespace = "walk"\nframe_index = 1\nframe_interval = 0.75\n'
            'pixels = """\n.#\n##\n"""\n\n',
            replace='',
        )
        saved_directory = tmp_path / 'saved'
        saved_directory.mkdir()
        with pytest.raises(AssertionError, match=r'walker\.toml.*frames'):
            sprite_files.check_pixels_survive_a_save_round_trip(
                sprite_file=sprite_file, directory=saved_directory
            )


class TestMetadata:
    """check_metadata_survives_a_save_round_trip."""

    def test_a_faithful_save_passes(self, tmp_path):
        """Name, description, frame_anchor and hitbox written and reloaded are the same."""
        sprite_file = write_sprite(directory=tmp_path, name='rock.toml', text=STATIC_SPRITE)
        saved_directory = tmp_path / 'saved'
        saved_directory.mkdir()
        sprite_files.check_metadata_survives_a_save_round_trip(
            sprite_file=sprite_file, directory=saved_directory
        )

    def test_a_dropped_description_fails(self, tmp_path, mocker):
        """A save that drops the description fails, naming the file."""
        sprite_file = write_sprite(directory=tmp_path, name='rock.toml', text=STATIC_SPRITE)
        save_altered(mocker=mocker, find='A grey rock.', replace='')
        saved_directory = tmp_path / 'saved'
        saved_directory.mkdir()
        with pytest.raises(AssertionError, match=r'rock\.toml'):
            sprite_files.check_metadata_survives_a_save_round_trip(
                sprite_file=sprite_file, directory=saved_directory
            )


class TestTransitions:
    """check_transitions_survive_a_save_round_trip."""

    def test_a_faithful_save_passes(self, tmp_path):
        """Transitions written back as read pass."""
        sprite_file = write_sprite(directory=tmp_path, name='walker.toml', text=ANIMATED_SPRITE)
        saved_directory = tmp_path / 'saved'
        saved_directory.mkdir()
        sprite_files.check_transitions_survive_a_save_round_trip(
            sprite_file=sprite_file, directory=saved_directory
        )

    def test_a_sprite_without_transitions_passes(self, tmp_path):
        """No transitions before and none after pass."""
        sprite_file = write_sprite(directory=tmp_path, name='rock.toml', text=STATIC_SPRITE)
        saved_directory = tmp_path / 'saved'
        saved_directory.mkdir()
        sprite_files.check_transitions_survive_a_save_round_trip(
            sprite_file=sprite_file, directory=saved_directory
        )

    def test_dropped_transitions_fail(self, tmp_path, mocker):
        """A writer that drops the [[transition]] sections fails, naming the file."""
        sprite_file = write_sprite(directory=tmp_path, name='walker.toml', text=ANIMATED_SPRITE)
        save_altered(
            mocker=mocker, find='[[transition]]\nfrom = "walk"\nto = "walk"\n\n', replace=''
        )
        saved_directory = tmp_path / 'saved'
        saved_directory.mkdir()
        with pytest.raises(AssertionError, match=r'walker\.toml'):
            sprite_files.check_transitions_survive_a_save_round_trip(
                sprite_file=sprite_file, directory=saved_directory
            )


class TestAnimatedSpriteFiles:
    """animated_sprite_files."""

    def test_only_files_with_an_animation_are_returned_sorted_across_directories(self, tmp_path):
        """Animated sprites from every directory come back, each directory sorted."""
        first = tmp_path / 'first'
        second = tmp_path / 'second'
        first.mkdir()
        second.mkdir()
        write_sprite(directory=first, name='b_static.toml', text=STATIC_SPRITE)
        animated_b = write_sprite(directory=first, name='b.toml', text=ANIMATED_SPRITE)
        animated_a = write_sprite(directory=first, name='a.toml', text=ANIMATED_SPRITE)
        animated_c = write_sprite(directory=second, name='c.toml', text=ONE_FRAME_ANIMATED_SPRITE)
        write_sprite(directory=second, name='notes.txt', text='[[animation]]')

        assert sprite_files.animated_sprite_files(directories=[first, second]) == [
            animated_a,
            animated_b,
            animated_c,
        ]

    def test_no_directories_give_no_files(self):
        """Nothing in, nothing out."""
        assert sprite_files.animated_sprite_files(directories=[]) == []
