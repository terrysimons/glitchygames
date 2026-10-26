"""Test suite for example sprites in glitchygames/examples/resources/sprites.

This module tests loading all the TOML sprite files from the examples directory
and verifies they work correctly with the TOML-only implementation.
"""

import logging
import tempfile
import time
from pathlib import Path

import numpy as np
import pygame
import pytest

from glitchygames.display_mode import set_display_mode
from glitchygames.sprites import SpriteFactory
from tests.harness import imported_engine_directory

# The imported engine's directory (installed: never the source tree by accident)
ENGINE_PACKAGE_DIRECTORY = imported_engine_directory()

# Constants for test thresholds
PIXEL_INTEGRITY_THRESHOLD = 100.0  # every pixel draws exactly as expected
MAX_REASONABLE_DIMENSION = 1000
MAX_ASPECT_RATIO = 10.0
MIN_ASPECT_RATIO = 0.1
MAX_LOAD_TIME = 1.0
MAX_RENDER_TIME = 0.1

LOG = logging.getLogger(__name__)


def _load_example_sprite(sprite_file):
    """Load an example sprite.

    Returns:
        The sprite, or None after an expected load error (logged). An unexpected error fails
        the test.

    """
    try:
        sprite = SpriteFactory.load_sprite(filename=str(sprite_file))
    except (ValueError, FileNotFoundError, AttributeError) as e:
        LOG.warning('Skipping sprite %s due to expected error: %s', sprite_file.name, e)
        return None
    except (TypeError, KeyError, OSError) as e:
        pytest.fail(f'Unexpected error loading sprite {sprite_file.name}: {e}')
    return sprite


class TestExamplesSprites:
    """Test example sprites from the glitchygames/examples/resources/sprites directory."""

    def setup_method(self):
        """Set up test fixtures."""
        pygame.init()
        set_display_mode(size=(800, 600))
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Path to the examples sprites directory
        self.sprites_dir = ENGINE_PACKAGE_DIRECTORY / 'examples' / 'resources' / 'sprites'

        # Get all TOML files in the directory
        self.toml_files = []
        if self.sprites_dir.exists():
            for file_path in self.sprites_dir.glob('*.toml'):
                self.toml_files.append(file_path)

    def test_load_all_toml_sprites(self):
        """Test that all TOML sprite files can be loaded."""
        if not self.sprites_dir.exists():
            pytest.skip(f'Sprites directory {self.sprites_dir} not found')

        loaded_count = 0

        for sprite_file in self.toml_files:
            # Load the sprite
            sprite = _load_example_sprite(sprite_file)
            if sprite is None:
                continue

            # Verify basic properties
            assert sprite.image is not None, f'Sprite {sprite_file.name} should have an image'
            assert isinstance(sprite.image, pygame.Surface), (
                f'Sprite {sprite_file.name} image should be a Surface'
            )

            # Check dimensions
            width, height = sprite.image.get_size()
            assert width > 0, f'Sprite {sprite_file.name} width should be positive'
            assert height > 0, f'Sprite {sprite_file.name} height should be positive'

            loaded_count += 1

        # Verify we loaded at least some sprites
        assert loaded_count > 0, 'Should load at least one example sprite'

    def test_sprite_pixel_integrity(self):
        """Test pixel data integrity for a sample of sprites."""
        if not self.sprites_dir.exists():
            pytest.skip(f'Sprites directory {self.sprites_dir} not found')

        # Test a sample of sprites for pixel integrity
        test_sprites = [
            'battle_axe.toml',
            'berry_bush.toml',
            'big_heart.toml',
            'book.toml',
            'colors.toml',
        ]

        for sprite_name in test_sprites:
            sprite_file = self.sprites_dir / sprite_name
            if not sprite_file.exists():
                continue

            # Load sprite
            sprite = _load_example_sprite(sprite_file)
            if sprite is None:
                continue

            # Test pixel integrity: every visible pixel is drawn as it is, and transparent
            # pixels (magenta keyed out, alpha 0) show the background (BUGS.md #133)
            assert sprite.image is not None
            background_color = (0, 0, 0)
            original_pixels = self._expected_drawn_pixels(
                surface=sprite.image, background_color=background_color
            )

            # Draw to a test surface: 32-bit without per-pixel alpha, so the result does not
            # depend on the display's pixel format
            test_surface = pygame.Surface(sprite.image.get_size(), depth=32)
            test_surface.fill(background_color)
            test_surface.blit(sprite.image, (0, 0))

            drawn_pixels = self._extract_pixel_data(test_surface)

            # Calculate match percentage
            pixel_matches = np.all(original_pixels == drawn_pixels, axis=2)
            match_percentage = float(pixel_matches.mean()) * 100

            assert match_percentage >= PIXEL_INTEGRITY_THRESHOLD, (
                f'Pixel integrity too low for {sprite_name}: {match_percentage:.1f}%'
            )

    def test_sprite_dimensions_consistency(self):
        """Test that sprite dimensions are consistent and reasonable."""
        if not self.sprites_dir.exists():
            pytest.skip(f'Sprites directory {self.sprites_dir} not found')

        # Test a sample of sprites
        test_sprites = [
            'battle_axe.toml',
            'berry_bush.toml',
            'big_heart.toml',
            'book.toml',
            'colors.toml',
            'dirt.toml',
            'grass1.toml',
            'key.toml',
            'sword.toml',
        ]

        for sprite_name in test_sprites:
            sprite_file = self.sprites_dir / sprite_name
            if not sprite_file.exists():
                continue

            sprite = _load_example_sprite(sprite_file)
            if sprite is None:
                continue
            assert sprite.image is not None
            width, height = sprite.image.get_size()

            # Check dimensions are reasonable
            assert width > 0, f'{sprite_name} width should be positive'
            assert height > 0, f'{sprite_name} height should be positive'
            assert width < MAX_REASONABLE_DIMENSION, f'{sprite_name} width should be reasonable'
            assert height < MAX_REASONABLE_DIMENSION, f'{sprite_name} height should be reasonable'

            # Check aspect ratio is reasonable
            aspect_ratio = width / height if height > 0 else 1
            assert aspect_ratio < MAX_ASPECT_RATIO, f'{sprite_name} aspect ratio too wide'
            assert aspect_ratio > MIN_ASPECT_RATIO, f'{sprite_name} aspect ratio too tall'

    def test_animated_sprites(self):
        """Test animated sprites in the examples directory."""
        if not self.sprites_dir.exists():
            pytest.skip(f'Sprites directory {self.sprites_dir} not found')

        # Look for animated sprites (colors.toml is known to be animated)
        animated_sprites = ['colors.toml']

        for sprite_name in animated_sprites:
            sprite_file = self.sprites_dir / sprite_name
            if not sprite_file.exists():
                continue

            sprite = _load_example_sprite(sprite_file)
            if sprite is None:
                continue

            # Check if it's an animated sprite
            if hasattr(sprite, 'animations'):
                assert sprite.animations is not None, (
                    f'Animated sprite {sprite_name} should have animations'
                )
                assert len(sprite.animations) > 0, (
                    f'Animated sprite {sprite_name} should have at least one animation'
                )

                # Check each animation
                for anim_name, frames in sprite.animations.items():
                    assert frames is not None, f'Animation {anim_name} should have frames'
                    assert len(frames) > 0, f'Animation {anim_name} should have at least one frame'

                    # Check each frame
                    for i, frame in enumerate(frames):
                        assert frame.image is not None, (
                            f'Frame {i} in {anim_name} should have an image'
                        )
                        assert isinstance(frame.image, pygame.Surface), (
                            f'Frame {i} in {anim_name} should be a Surface'
                        )

    def test_sprite_performance(self):
        """Test sprite loading and rendering performance."""
        if not self.sprites_dir.exists():
            pytest.skip(f'Sprites directory {self.sprites_dir} not found')

        # Test a sample of sprites for performance
        test_sprites = [
            'battle_axe.toml',
            'berry_bush.toml',
            'big_heart.toml',
            'book.toml',
            'colors.toml',
        ]

        for sprite_name in test_sprites:
            sprite_file = self.sprites_dir / sprite_name
            if not sprite_file.exists():
                continue

            # Time the loading
            start_time = time.time()
            sprite = _load_example_sprite(sprite_file)
            if sprite is None:
                continue
            load_time = time.time() - start_time

            # Time the rendering
            assert sprite.image is not None
            start_time = time.time()
            test_surface = pygame.Surface(sprite.image.get_size(), depth=32)
            test_surface.blit(sprite.image, (0, 0))
            render_time = time.time() - start_time

            # Verify performance is reasonable
            assert load_time < MAX_LOAD_TIME, f'{sprite_name} loading too slow: {load_time:.3f}s'
            assert render_time < MAX_RENDER_TIME, (
                f'{sprite_name} rendering too slow: {render_time:.3f}s'
            )

    @staticmethod
    def _expected_drawn_pixels(*, surface, background_color):
        """Return the RGB pixels a surface should draw over an opaque background.

        A fully transparent pixel (alpha 0, or the surface's colorkey) shows the background;
        any other pixel keeps its own RGB (the sampled sprites have no translucent colors).

        Returns:
            np.ndarray: The expected pixels, a (width, height, 3) array.

        """
        rgb_pixels = pygame.surfarray.array3d(surface)
        is_transparent = np.zeros(surface.get_size(), dtype=bool)
        if surface.get_flags() & pygame.SRCALPHA:
            is_transparent |= pygame.surfarray.array_alpha(surface) == 0
        colorkey = surface.get_colorkey()
        if colorkey is not None:
            is_transparent |= np.all(rgb_pixels == colorkey[:3], axis=2)
        rgb_pixels[is_transparent] = background_color
        return rgb_pixels

    @staticmethod
    def _extract_pixel_data(surface):
        """Extract a surface's RGB pixels in bulk.

        Returns:
            np.ndarray: A (width, height, 3) array.

        """
        return pygame.surfarray.array3d(surface)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


# The engine's sprites. A game moved into its own package checks its sprites with these tests
# from its own tests (Papyrus's: src/games/brave-adventurer/tests/papyrus/)
BUNDLED_SPRITE_FILES = sorted([
    *(ENGINE_PACKAGE_DIRECTORY / 'examples').glob('**/sprites/*.toml'),
    *(ENGINE_PACKAGE_DIRECTORY / 'assets').glob('*.toml'),
])


def _sprite_file_test_id(sprite_file: Path) -> str:
    """Name a bundled sprite file relative to the engine (the same id under nox and uv run).

    Returns:
        str: The file's path inside the engine package, e.g. ``assets/eraser.toml``.

    """
    return sprite_file.relative_to(ENGINE_PACKAGE_DIRECTORY).as_posix()


def _pixel_blocks(sprite_data: dict) -> list[tuple[str, str]]:
    """Return (label, pixels) for the static sprite and every animation frame in a sprite file.

    Returns:
        list[tuple[str, str]]: One entry per pixel block, labelled for failure messages.

    """
    blocks: list[tuple[str, str]] = []
    static_pixels = sprite_data.get('sprite', {}).get('pixels')
    if static_pixels is not None:
        blocks.append(('sprite', static_pixels))
    for animation_index, animation in enumerate(sprite_data.get('animation', [])):
        for frame_index, frame in enumerate(animation.get('frame', [])):
            if 'pixels' in frame:
                label = f'animation {animation_index} frame {frame_index}'
                blocks.append((label, frame['pixels']))
    return blocks


@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_sprite_rows_have_equal_lengths(sprite_file):
    """Every pixel row in a bundled sprite is the same width.

    The loader pads a short row with its last character (and truncates a long one), which
    silently changes the art, e.g. a 9-wide row in gold_scarab.toml frame 2 drew a notch.
    """
    import tomllib

    from glitchygames.sprites import AnimatedSprite

    sprite_data = tomllib.loads(sprite_file.read_text(encoding='utf-8'))
    for label, pixels in _pixel_blocks(sprite_data):
        rows = AnimatedSprite.parse_toml_pixel_lines(pixels)
        row_lengths = {len(row) for row in rows}
        assert len(row_lengths) <= 1, f'{sprite_file} {label}: row lengths {sorted(row_lengths)}'


ANIMATED_SPRITE_FILES = [
    sprite_file
    for sprite_file in BUNDLED_SPRITE_FILES
    if '[[animation]]' in sprite_file.read_text(encoding='utf-8')
]
DEFAULT_TOML_FRAME_INTERVAL = 0.5


def _animation_timings(sprite_data: dict) -> list[tuple[str, float, bool, list[float | None]]]:
    """Return each animation's timing as written in a sprite file.

    Returns:
        list[tuple[str, float, bool, list[float | None]]]: (namespace, frame_interval, loop,
        per-frame frame_interval overrides in frame_index order, None where absent).

    """
    timings: list[tuple[str, float, bool, list[float | None]]] = []
    for animation in sprite_data.get('animation', []):
        frames = sorted(animation.get('frame', []), key=lambda frame: frame.get('frame_index', 0))
        timings.append((
            animation.get('namespace', 'default'),
            animation.get('frame_interval', DEFAULT_TOML_FRAME_INTERVAL),
            animation.get('loop', True),
            [frame.get('frame_interval') for frame in frames],
        ))
    return timings


@pytest.fixture
def real_display():
    """Give AnimatedSprite a real display for loading and saving."""
    pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(96, 64))


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', ANIMATED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_animation_timings_survive_a_save_round_trip(sprite_file, tmp_path):
    """Load -> save writes each animation's frame_interval, loop and per-frame overrides back.

    The writer used to hard-code frame_interval = 0.5 and loop = true, so saving (Bitmappy
    saves this way) lost every animation's timing.
    """
    import tomllib

    from glitchygames.sprites import AnimatedSprite

    original_sprite = AnimatedSprite(str(sprite_file))
    if original_sprite.get_total_frame_count() == 1:
        pytest.skip('single-frame sprites are saved in the static format, without timing')
    saved_file = tmp_path / sprite_file.name
    original_sprite.save(str(saved_file), 'toml')

    original_data = tomllib.loads(sprite_file.read_text(encoding='utf-8'))
    saved_data = tomllib.loads(saved_file.read_text(encoding='utf-8'))
    assert _animation_timings(saved_data) == _animation_timings(original_data)

    reloaded_sprite = AnimatedSprite(str(saved_file))
    for animation_name, frames in original_sprite._animations.items():
        reloaded_durations = [
            frame.duration for frame in reloaded_sprite._animations[animation_name]
        ]
        assert reloaded_durations == [frame.duration for frame in frames], animation_name


def _hitbox_sections(sprite_data: dict) -> tuple[dict | None, list[dict | None]]:
    """Return the hitboxes a sprite file defines explicitly.

    Returns:
        tuple[dict | None, list[dict | None]]: The [sprite.hitbox] table (or None) and each
        animation frame's [animation.frame.hitbox] (None where absent), in file order with
        frames in frame_index order.

    """
    frame_hitboxes: list[dict | None] = []
    for animation in sprite_data.get('animation', []):
        frames = sorted(animation.get('frame', []), key=lambda frame: frame.get('frame_index', 0))
        frame_hitboxes.extend(frame.get('hitbox') for frame in frames)
    return sprite_data.get('sprite', {}).get('hitbox'), frame_hitboxes


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_hitboxes_survive_a_save_round_trip_unchanged(sprite_file, tmp_path):
    """Save writes exactly the hitboxes the file defined: none are synthesised.

    The writer used to turn the visible-pixel fallback into explicit [sprite.hitbox] and
    [animation.frame.hitbox] sections, so saving a sprite without hitboxes froze them.
    """
    import tomllib

    from glitchygames.sprites import AnimatedSprite

    original_sprite = AnimatedSprite(str(sprite_file))
    original_data = tomllib.loads(sprite_file.read_text(encoding='utf-8'))
    if original_sprite.get_total_frame_count() == 1 and 'animation' in original_data:
        pytest.skip('a one-frame animation is saved in the static format')
    saved_file = tmp_path / sprite_file.name
    original_sprite.save(str(saved_file), 'toml')

    saved_data = tomllib.loads(saved_file.read_text(encoding='utf-8'))
    assert _hitbox_sections(saved_data) == _hitbox_sections(original_data)


def _rgba_frames(sprite) -> dict[tuple[str, int], tuple[tuple[int, int], list[tuple[int, ...]]]]:
    """Return every frame's size and pixels as RGBA tuples (RGB pixels get alpha 255).

    Returns:
        dict: (animation name, frame position) -> (size, RGBA pixels).

    """
    frames = {}
    for animation_name, animation_frames in sprite._animations.items():
        for frame_position, frame in enumerate(animation_frames):
            rgba_pixels = [
                pixel if len(pixel) == 4 else (*pixel, 255) for pixel in frame.get_pixel_data()
            ]
            frames[animation_name, frame_position] = (frame.get_size(), rgba_pixels)
    return frames


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_sprite_pixels_survive_a_save_round_trip(sprite_file, tmp_path):
    """Load -> save -> reload gives every frame (static and animated) the same pixels."""
    from glitchygames.sprites import AnimatedSprite

    original_sprite = AnimatedSprite(str(sprite_file))
    saved_file = tmp_path / sprite_file.name
    original_sprite.save(str(saved_file), 'toml')
    reloaded_sprite = AnimatedSprite(str(saved_file))

    original_frames = _rgba_frames(original_sprite)
    reloaded_frames = list(_rgba_frames(reloaded_sprite).values())
    # A one-frame sprite is saved in the static format, which may rename its animation
    assert len(reloaded_frames) == len(original_frames)
    for (frame_key, original_frame), reloaded_frame in zip(
        original_frames.items(), reloaded_frames, strict=True
    ):
        assert reloaded_frame == original_frame, frame_key


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_sprite_metadata_survives_a_save_round_trip(sprite_file, tmp_path):
    """Load -> save -> reload keeps the [sprite] name, description, frame_anchor and hitbox.

    The single-frame (static) writer used to drop description.
    """
    from glitchygames.sprites import AnimatedSprite

    original_sprite = AnimatedSprite(str(sprite_file))
    saved_file = tmp_path / sprite_file.name
    original_sprite.save(str(saved_file), 'toml')
    reloaded_sprite = AnimatedSprite(str(saved_file))

    def metadata(sprite):
        return (sprite.name, sprite.description, sprite.frame_anchor, sprite.hitbox)

    assert metadata(reloaded_sprite) == metadata(original_sprite)


@pytest.mark.usefixtures('real_display')
def test_static_sprite_metadata_survives_a_save_round_trip(tmp_path):
    """A single-frame sprite keeps name, description, frame_anchor and hitbox when saved."""
    from glitchygames.sprites import AnimatedSprite

    sprite_file = tmp_path / 'static.toml'
    sprite_file.write_text(
        '[sprite]\nname = "rock"\ndescription = """A grey rock.\nIt does not move."""\n'
        'frame_anchor = "bottom"\npixels = """\n#.\n##\n"""\n\n'
        '[sprite.hitbox]\noffset_x = 0\noffset_y = 0\nwidth = 2\nheight = 2\n\n'
        '[colors."#"]\nred = 90\ngreen = 90\nblue = 90\n\n'
        '[colors."."]\nred = 255\ngreen = 0\nblue = 255\n',
        encoding='utf-8',
    )
    original_sprite = AnimatedSprite(str(sprite_file))
    saved_file = tmp_path / 'resaved.toml'
    original_sprite.save(str(saved_file), 'toml')
    reloaded_sprite = AnimatedSprite(str(saved_file))

    assert reloaded_sprite.description == 'A grey rock.\nIt does not move.'
    assert (reloaded_sprite.name, reloaded_sprite.frame_anchor, reloaded_sprite.hitbox) == (
        original_sprite.name,
        original_sprite.frame_anchor,
        original_sprite.hitbox,
    )


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_transitions_survive_a_save_round_trip(sprite_file, tmp_path):
    """Load -> save writes every [[transition]] back with the same keys, values and order.

    The writers used to drop them, so saving (e.g. from Bitmappy) lost the animation state
    machine (cobra 2 -> 0 transitions, Papyrus player 6 -> 0).
    """
    import tomllib

    from glitchygames.sprites import AnimatedSprite

    original_data = tomllib.loads(sprite_file.read_text(encoding='utf-8'))
    saved_file = tmp_path / sprite_file.name
    AnimatedSprite(str(sprite_file)).save(str(saved_file), 'toml')

    saved_data = tomllib.loads(saved_file.read_text(encoding='utf-8'))
    assert saved_data.get('transition', []) == original_data.get('transition', [])


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('frame_count', [1, 2], ids=['single-frame-writer', 'animated-writer'])
def test_names_and_descriptions_needing_escapes_round_trip(frame_count, tmp_path):
    """Quotes, backslashes, triple quotes and a leading newline survive both writers."""
    import pygame as real_pygame

    from glitchygames.sprites import AnimatedSprite, SpriteFrame

    sprite = AnimatedSprite()
    frames = [SpriteFrame(real_pygame.Surface((2, 2))) for _ in range(frame_count)]
    for frame in frames:
        frame.pixels = [(0, 0, 0)] * 4
    sprite.add_animation('idle', frames)
    sprite.name = 'say "hi" \\ bye'
    sprite.description = '\nFirst line with """triple quotes""" and a \\ backslash.\nSecond line.'
    saved_file = tmp_path / 'escapes.toml'

    sprite.save(str(saved_file), 'toml')
    reloaded_sprite = AnimatedSprite(str(saved_file))

    assert (reloaded_sprite.name, reloaded_sprite.description) == (
        sprite.name,
        sprite.description,
    )
