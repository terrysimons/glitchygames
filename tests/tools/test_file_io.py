"""Tests for glitchygames.bitmappy.file_io.FileIOManager.

Covers drop handling (film strips, the canvas, PNG and TOML files), the PNG-to-TOML conversion
pipeline on real PNG files written to tmp_path, TOML validation, and loading a converted sprite's
first frame into the canvas.
"""

import logging
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pygame
import pytest

from glitchygames.bitmappy.file_io import FileIOManager
from glitchygames.bitmappy.onion_skinning import get_onion_skinning_manager
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.sprites.frame import SpriteFrame

# A minimal valid converted sprite, as the PNG conversion writes it
CONVERTED_TOML = (
    '[sprite]\nname = "imported_from_x"\npixels = """\n#\n"""\n\n'
    '[colors]\n[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n'
)


def _write_png(*, path: Path, size: tuple[int, int], fill: tuple[int, ...]) -> Path:
    """Write a solid-color PNG file.

    Returns:
        The path written.

    """
    # Explicit depths: a plain Surface takes the display's format, which has an alpha channel
    # on real video drivers, so an RGB fill would be saved as RGBA there
    surface = (
        pygame.Surface(size, pygame.SRCALPHA, 32) if len(fill) == 4 else pygame.Surface(size, 0, 24)
    )
    surface.fill(fill)
    pygame.image.save(surface, str(path))
    return path


def _drop_event(*, file_path: Path | str) -> SimpleNamespace:
    """Build a drop event carrying a file path.

    Returns:
        An object with the ``file`` attribute of a DROPFILE event.

    """
    return SimpleNamespace(file=str(file_path))


def _set_mouse_position(*, position: tuple[int, int]) -> None:
    """Make the frame's polled mouse position ``position``."""
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(),
            modifiers=0,
            mouse_position=position,
            mouse_buttons=(False, False, False),
            mouse_focused=True,
        ),
    )


class FakeMiniView:
    """The canvas mini view: pixels, dirty flags and redraw count."""

    def __init__(self) -> None:
        """Start with no pixels and no redraws."""
        self.pixels: list[tuple[int, ...]] = []
        self.dirty_pixels: list[bool] = []
        self.dirty = 0
        self.redraw_count = 0

    def force_redraw(self) -> None:
        """Count a redraw."""
        self.redraw_count += 1


class FakeAnimatedSprite:
    """An animated sprite with named animations of real SpriteFrames."""

    def __init__(self, animations: dict[str, list[SpriteFrame]]) -> None:
        """Hold the animations by name."""
        self._animations = animations


class FakeCanvasSprite:
    """A canvas sprite that loads a fixed animated sprite on on_load_file_event."""

    def __init__(
        self,
        *,
        animated_sprite: FakeAnimatedSprite | None,
        mini_view: FakeMiniView | None = None,
    ) -> None:
        """Remember the sprite to load and start with an empty canvas."""
        self._sprite_to_load = animated_sprite
        self.animated_sprite: FakeAnimatedSprite | None = None
        self.mini_view = mini_view
        self.loaded_paths: list[str] = []
        self.pixels: list[tuple[int, ...]] = []
        self.dirty_pixels: list[bool] = []
        self.dirty = 0
        self.redraw_count = 0
        self.border_updates = 0

    def on_load_file_event(self, event: object) -> None:
        """Load the configured sprite, remembering the requested path."""
        self.loaded_paths.append(event.text)  # type: ignore[attr-defined]
        self.animated_sprite = self._sprite_to_load

    def _update_border_thickness(self) -> None:
        """Count border updates."""
        self.border_updates += 1

    def force_redraw(self) -> None:
        """Count redraws."""
        self.redraw_count += 1


def _two_by_one_frame() -> SpriteFrame:
    """Build a 2x1 frame: a transparent magenta pixel and an opaque red one.

    Returns:
        The frame.

    """
    surface = pygame.Surface((2, 1), pygame.SRCALPHA)
    surface.set_at((0, 0), (255, 0, 255, 0))
    surface.set_at((1, 0), (255, 0, 0, 255))
    return SpriteFrame(surface)


class RgbColor(tuple):
    """A three-component color with r, g and b attributes, like an RGB surface's colors."""

    __slots__ = ()

    @property
    def r(self) -> int:
        """Red component."""
        return self[0]

    @property
    def g(self) -> int:
        """Green component."""
        return self[1]

    @property
    def b(self) -> int:
        """Blue component."""
        return self[2]


class RgbSurface:
    """A one-pixel surface whose get_at returns a three-component color."""

    def __init__(self, *, color: RgbColor) -> None:
        """Hold the single pixel's color."""
        self.color = color

    def get_size(self) -> tuple[int, int]:
        """Return the one-pixel size.

        Returns:
            (1, 1).

        """
        return (1, 1)

    def get_at(self, position: tuple[int, int]) -> RgbColor:
        """Return the pixel's color.

        Returns:
            The color.

        """
        return self.color


@pytest.fixture
def restore_onion_skinning():
    """Restore the global onion skinning manager's state after the test.

    Yields:
        The global onion skinning manager.

    """
    manager = get_onion_skinning_manager()
    saved_global = manager.global_onion_skinning_enabled
    saved_frames = {name: dict(states) for name, states in manager.onion_skinning_enabled.items()}
    yield manager
    manager.global_onion_skinning_enabled = saved_global
    manager.onion_skinning_enabled.clear()
    manager.onion_skinning_enabled.update(saved_frames)


class TestOnDropFileEvent:
    """Test on_drop_file_event routing."""

    def test_missing_file_is_ignored(self, tmp_path):
        """A path that cannot be stat'ed stops the drop before any handler runs."""
        film_strip = SimpleNamespace(on_drop_file_event=pytest.fail)
        editor = SimpleNamespace(film_strip_sprites={'strip': film_strip})

        FileIOManager(editor).on_drop_file_event(_drop_event(file_path=tmp_path / 'missing.png'))

    def test_film_strip_that_handles_the_drop_wins(self, tmp_path):
        """The first film strip returning True consumes the drop; the canvas is not asked."""
        dropped_file = tmp_path / 'sprite.toml'
        dropped_file.write_text(CONVERTED_TOML, encoding='utf-8')
        handled_events: list[object] = []

        def handle(event: object) -> bool:
            handled_events.append(event)
            return True

        editor = SimpleNamespace(
            film_strip_sprites={
                'no handler': object(),
                'declines': SimpleNamespace(on_drop_file_event=lambda event: False),
                'handles': SimpleNamespace(on_drop_file_event=handle),
            },
            canvas=None,
        )
        event = _drop_event(file_path=dropped_file)

        FileIOManager(editor).on_drop_file_event(event)

        assert handled_events == [event]

    def test_film_strip_error_moves_on_to_the_next_strip(self, tmp_path):
        """A film strip that raises is logged and the next strip still gets the drop."""
        dropped_file = tmp_path / 'sprite.toml'
        dropped_file.write_text(CONVERTED_TOML, encoding='utf-8')
        handled_events: list[object] = []

        def broken(event: object) -> bool:
            msg = 'broken strip'
            raise ValueError(msg)

        def handle(event: object) -> bool:
            handled_events.append(event)
            return True

        editor = SimpleNamespace(
            film_strip_sprites={
                'broken': SimpleNamespace(on_drop_file_event=broken),
                'handles': SimpleNamespace(on_drop_file_event=handle),
            },
        )

        assert FileIOManager(editor)._try_film_strip_drop(_drop_event(file_path=dropped_file))
        assert len(handled_events) == 1

    def test_no_film_strip_handles_it_returns_false(self):
        """With every strip declining, the film strip pass reports the drop unhandled."""
        editor = SimpleNamespace(
            film_strip_sprites={'declines': SimpleNamespace(on_drop_file_event=lambda e: False)},
        )

        assert FileIOManager(editor)._try_film_strip_drop(_drop_event(file_path='x')) is False

    def test_toml_dropped_on_the_canvas_is_loaded(self, tmp_path):
        """A TOML file dropped over the canvas is loaded into the canvas sprite."""
        dropped_file = tmp_path / 'sprite.toml'
        dropped_file.write_text(CONVERTED_TOML, encoding='utf-8')
        canvas_sprite = FakeCanvasSprite(animated_sprite=None)
        editor = SimpleNamespace(
            film_strip_sprites={},
            canvas=SimpleNamespace(rect=pygame.Rect(0, 0, 100, 100)),
            all_sprites=[object(), canvas_sprite],
        )
        _set_mouse_position(position=(10, 10))

        FileIOManager(editor).on_drop_file_event(_drop_event(file_path=dropped_file))

        assert canvas_sprite.loaded_paths == [str(dropped_file)]

    def test_drop_outside_the_canvas_is_ignored(self, tmp_path):
        """A file dropped away from the canvas loads nothing."""
        dropped_file = tmp_path / 'sprite.toml'
        dropped_file.write_text(CONVERTED_TOML, encoding='utf-8')
        canvas_sprite = FakeCanvasSprite(animated_sprite=None)
        editor = SimpleNamespace(
            canvas=SimpleNamespace(rect=pygame.Rect(0, 0, 100, 100)),
            all_sprites=[canvas_sprite],
        )
        _set_mouse_position(position=(500, 500))

        FileIOManager(editor).on_drop_file_event(_drop_event(file_path=dropped_file))

        assert canvas_sprite.loaded_paths == []

    def test_png_dropped_on_the_canvas_is_converted_then_loaded(self, tmp_path):
        """A PNG over the canvas is converted to a TOML next to it, which is then loaded."""
        png_path = _write_png(path=tmp_path / 'block.png', size=(2, 2), fill=(10, 20, 30))
        canvas_sprite = FakeCanvasSprite(animated_sprite=None)
        editor = SimpleNamespace(
            canvas=SimpleNamespace(
                rect=pygame.Rect(0, 0, 100, 100), pixels_across=2, pixels_tall=2
            ),
            all_sprites=[canvas_sprite],
        )
        _set_mouse_position(position=(1, 1))

        FileIOManager(editor).on_drop_file_event(_drop_event(file_path=png_path))

        converted_path = tmp_path / 'block.toml'
        assert canvas_sprite.loaded_paths == [str(converted_path)]
        assert tomllib.loads(converted_path.read_text(encoding='utf-8'))['colors'] == {
            '.': {'red': 10, 'green': 20, 'blue': 30},
        }

    def test_png_that_fails_to_convert_loads_nothing(self, tmp_path):
        """A file named .png that is not an image is reported and not loaded."""
        broken_png = tmp_path / 'broken.png'
        broken_png.write_text('not a png', encoding='utf-8')
        canvas_sprite = FakeCanvasSprite(animated_sprite=None)
        editor = SimpleNamespace(
            canvas=SimpleNamespace(rect=pygame.Rect(0, 0, 100, 100)),
            all_sprites=[canvas_sprite],
        )
        _set_mouse_position(position=(1, 1))

        FileIOManager(editor).on_drop_file_event(_drop_event(file_path=broken_png))

        assert canvas_sprite.loaded_paths == []
        assert not (tmp_path / 'broken.toml').exists()

    def test_unsupported_file_type_is_ignored(self, tmp_path):
        """A dropped .txt file over the canvas loads nothing."""
        text_file = tmp_path / 'notes.txt'
        text_file.write_text('hello', encoding='utf-8')
        canvas_sprite = FakeCanvasSprite(animated_sprite=None)
        editor = SimpleNamespace(
            canvas=SimpleNamespace(rect=pygame.Rect(0, 0, 100, 100)),
            all_sprites=[canvas_sprite],
        )
        _set_mouse_position(position=(1, 1))

        FileIOManager(editor).on_drop_file_event(_drop_event(file_path=text_file))

        assert canvas_sprite.loaded_paths == []


class TestConvertPngToBitmappy:
    """Test the PNG-to-TOML conversion pipeline."""

    def test_png_matching_the_canvas_converts_its_colors(self, tmp_path):
        """A canvas-sized two-color PNG becomes a TOML with one glyph per color."""
        png_path = tmp_path / 'two.png'
        surface = pygame.Surface((2, 1))
        surface.set_at((0, 0), (0, 0, 0))
        surface.set_at((1, 0), (255, 255, 255))
        pygame.image.save(surface, str(png_path))
        editor = SimpleNamespace(canvas=SimpleNamespace(pixels_across=2, pixels_tall=1))

        output_path = FileIOManager(editor)._convert_png_to_bitmappy(str(png_path))

        assert output_path == str(tmp_path / 'two.toml')
        data = tomllib.loads(Path(output_path).read_text(encoding='utf-8'))
        assert data['sprite']['name'] == 'imported_from_two'
        assert data['sprite']['pixels'] == '.a\n'
        assert data['colors'] == {
            '.': {'red': 0, 'green': 0, 'blue': 0},
            'a': {'red': 255, 'green': 255, 'blue': 255},
        }

    def test_png_is_resized_to_the_default_size_without_a_canvas(self, tmp_path):
        """Without a canvas the image is scaled to 32x32."""
        png_path = _write_png(path=tmp_path / 'small.png', size=(4, 4), fill=(1, 2, 3))

        output_path = FileIOManager(SimpleNamespace())._convert_png_to_bitmappy(str(png_path))

        assert output_path is not None
        pixels = tomllib.loads(Path(output_path).read_text(encoding='utf-8'))['sprite']['pixels']
        rows = pixels.rstrip('\n').split('\n')
        assert len(rows) == 32
        assert all(row == '.' * 32 for row in rows)

    def test_transparent_pixels_map_to_the_magenta_transparency_key(self, tmp_path, caplog):
        """A transparent pixel becomes magenta, not the white the image is flattened onto (#92)."""
        png_path = tmp_path / 'alpha.png'
        surface = pygame.Surface((2, 1), pygame.SRCALPHA)
        surface.set_at((0, 0), (0, 0, 0, 0))
        surface.set_at((1, 0), (0, 0, 0, 255))
        pygame.image.save(surface, str(png_path))
        editor = SimpleNamespace(canvas=SimpleNamespace(pixels_across=2, pixels_tall=1))
        caplog.set_level(logging.INFO, logger='game')

        output_path = FileIOManager(editor)._convert_png_to_bitmappy(str(png_path))

        assert output_path is not None
        data = tomllib.loads(Path(output_path).read_text(encoding='utf-8'))
        assert data['sprite']['pixels'] == '█.\n'
        assert data['colors'] == {
            '█': {'red': 255, 'green': 0, 'blue': 255},
            '.': {'red': 0, 'green': 0, 'blue': 0},
        }
        assert 'Found 1 transparent pixels, mapped to magenta' in caplog.text

    def test_opaque_white_next_to_a_transparent_pixel_stays_white(self, tmp_path):
        """Transparent pixels flatten to white, but opaque white pixels keep their color."""
        png_path = tmp_path / 'white.png'
        surface = pygame.Surface((2, 1), pygame.SRCALPHA)
        surface.set_at((0, 0), (255, 255, 255, 255))
        surface.set_at((1, 0), (0, 0, 0, 0))
        pygame.image.save(surface, str(png_path))
        editor = SimpleNamespace(canvas=SimpleNamespace(pixels_across=2, pixels_tall=1))

        output_path = FileIOManager(editor)._convert_png_to_bitmappy(str(png_path))

        assert output_path is not None
        data = tomllib.loads(Path(output_path).read_text(encoding='utf-8'))
        assert data['sprite']['pixels'] == '.█\n'
        assert data['colors']['.'] == {'red': 255, 'green': 255, 'blue': 255}

    def test_transparency_survives_resizing_to_the_canvas(self, tmp_path):
        """A resized alpha PNG keeps its transparent half transparent (#92)."""
        png_path = tmp_path / 'wide.png'
        surface = pygame.Surface((4, 2), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 255))
        surface.fill((0, 0, 0, 0), pygame.Rect(0, 0, 2, 2))
        pygame.image.save(surface, str(png_path))
        editor = SimpleNamespace(canvas=SimpleNamespace(pixels_across=2, pixels_tall=1))

        output_path = FileIOManager(editor)._convert_png_to_bitmappy(str(png_path))

        assert output_path is not None
        data = tomllib.loads(Path(output_path).read_text(encoding='utf-8'))
        assert data['sprite']['pixels'] == '█.\n'

    def test_opaque_pixels_of_an_alpha_png_keep_their_color(self, tmp_path):
        """An alpha PNG whose pixels are all opaque converts without magenta."""
        png_path = _write_png(path=tmp_path / 'opaque.png', size=(1, 1), fill=(9, 8, 7, 255))
        editor = SimpleNamespace(canvas=SimpleNamespace(pixels_across=1, pixels_tall=1))

        output_path = FileIOManager(editor)._convert_png_to_bitmappy(str(png_path))

        assert output_path is not None
        data = tomllib.loads(Path(output_path).read_text(encoding='utf-8'))
        assert data['colors'] == {'.': {'red': 9, 'green': 8, 'blue': 7}}

    def test_unreadable_png_returns_none(self, tmp_path):
        """A file that pygame cannot load converts to nothing."""
        broken_png = tmp_path / 'broken.png'
        broken_png.write_bytes(b'\x00\x01')

        assert FileIOManager(SimpleNamespace())._convert_png_to_bitmappy(str(broken_png)) is None


class TestDetectPngTransparency:
    """Test _detect_png_transparency."""

    def test_flattened_image_of_an_alpha_file_has_transparency(self, tmp_path):
        """The flattened (opaque) image of an alpha file is transparent: the file decides (#92)."""
        png_path = _write_png(path=tmp_path / 'alpha.png', size=(1, 1), fill=(5, 5, 5, 0))

        has_transparency, original_image = FileIOManager(
            SimpleNamespace()
        )._detect_png_transparency(pygame.Surface((1, 1)), str(png_path))

        assert has_transparency is True
        assert original_image is not None
        assert original_image.get_at((0, 0)).a == 0

    def test_original_image_is_scaled_to_the_converted_size(self, tmp_path):
        """The alpha image returned lines up with the resized image's pixels."""
        png_path = _write_png(path=tmp_path / 'alpha.png', size=(4, 4), fill=(5, 5, 5, 0))

        _, original_image = FileIOManager(SimpleNamespace())._detect_png_transparency(
            pygame.Surface((2, 3)),
            str(png_path),
        )

        assert original_image is not None
        assert original_image.get_size() == (2, 3)

    def test_opaque_file_has_no_transparency(self, tmp_path):
        """A file without an alpha channel is not transparent."""
        png_path = _write_png(path=tmp_path / 'opaque.png', size=(1, 1), fill=(5, 5, 5))

        result = FileIOManager(SimpleNamespace())._detect_png_transparency(
            pygame.Surface((1, 1)),
            str(png_path),
        )

        assert result == (False, None)

    def test_alpha_channel_with_only_opaque_pixels_has_no_transparency(self, tmp_path):
        """An alpha channel alone is not transparency: no pixel is below the threshold.

        Paint programs often export RGBA files whose pixels are all opaque, and a pygame
        Surface takes the display's format, which has alpha on real video drivers (cocoa).
        """
        png_path = _write_png(path=tmp_path / 'opaque-rgba.png', size=(2, 2), fill=(5, 5, 5, 255))

        result = FileIOManager(SimpleNamespace())._detect_png_transparency(
            pygame.Surface((2, 2)),
            str(png_path),
        )

        assert result == (False, None)


class TestSamplePngColors:
    """Test _sample_png_colors."""

    def test_transparent_pixels_are_counted_and_replaced_by_magenta(self):
        """With an alpha original, transparent pixels count and their color becomes magenta."""
        image = pygame.Surface((2, 1))
        image.set_at((0, 0), (255, 255, 255))
        image.set_at((1, 0), (0, 0, 0))
        original_image = pygame.Surface((2, 1), pygame.SRCALPHA)
        original_image.set_at((0, 0), (255, 255, 255, 0))
        original_image.set_at((1, 0), (0, 0, 0, 255))
        pixel_array = pygame.surfarray.array3d(image)

        unique_colors, sample_count, transparent_pixels = FileIOManager(
            SimpleNamespace()
        )._sample_png_colors(
            pixel_array,
            2,
            1,
            has_transparency=True,
            original_image=original_image,
        )

        assert unique_colors == {(255, 0, 255), (0, 0, 0)}
        assert sample_count == 2
        assert transparent_pixels == 1

    def test_large_images_are_sampled_sparsely(self):
        """An image over 10k pixels is sampled with a step above one."""
        image = pygame.Surface((200, 200))
        pixel_array = pygame.surfarray.array3d(image)

        _, sample_count, _ = FileIOManager(SimpleNamespace())._sample_png_colors(
            pixel_array,
            200,
            200,
            has_transparency=False,
            original_image=None,
        )

        # step = 40000 // 10000 = 4, so 50 x 50 samples
        assert sample_count == 2500


class TestValidateTomlContent:
    """Test _validate_toml_content."""

    def test_valid_content_passes(self, tmp_path):
        """A file with sprite, colors and a color definition validates."""
        toml_path = tmp_path / 'ok.toml'
        toml_path.write_text(CONVERTED_TOML, encoding='utf-8')

        FileIOManager(SimpleNamespace())._validate_toml_content(toml_path)

    @pytest.mark.parametrize(
        ('content', 'message'),
        [
            ('[colors]\n[colors."#"]\n', 'no \\[sprite\\] section'),
            ('[sprite]\n', 'no \\[colors\\] section'),
            ('[sprite]\n[colors]\n', 'no color definitions'),
        ],
    )
    def test_incomplete_content_raises_value_error(self, tmp_path, content, message):
        """Missing sections or color definitions are rejected."""
        toml_path = tmp_path / 'bad.toml'
        toml_path.write_text(content, encoding='utf-8')

        with pytest.raises(ValueError, match=message):
            FileIOManager(SimpleNamespace())._validate_toml_content(toml_path)


class TestLoadConvertedSprite:
    """Test loading a converted sprite into the canvas."""

    def test_first_frame_pixels_reach_the_canvas_and_mini_view(self, restore_onion_skinning):
        """The first frame's pixels are copied, transparent magenta made opaque."""
        mini_view = FakeMiniView()
        canvas_sprite = FakeCanvasSprite(
            animated_sprite=FakeAnimatedSprite({'idle': [_two_by_one_frame()]}),
            mini_view=mini_view,
        )
        editor = SimpleNamespace(all_sprites=[canvas_sprite])

        FileIOManager(editor)._load_converted_sprite('sprite.toml')

        expected_pixels = [(255, 0, 255, 255), (255, 0, 0, 255)]
        assert canvas_sprite.loaded_paths == ['sprite.toml']
        assert canvas_sprite.pixels == expected_pixels
        assert canvas_sprite.dirty_pixels == [True, True]
        assert canvas_sprite.border_updates == 1
        assert canvas_sprite.dirty == 1
        assert mini_view.pixels == expected_pixels
        assert mini_view.pixels is not canvas_sprite.pixels
        assert mini_view.dirty == 1
        assert mini_view.redraw_count == 1

    def test_onion_skinning_is_set_for_every_frame_but_the_first(self, restore_onion_skinning):
        """Loading enables onion skinning on frames after the first and globally."""
        restore_onion_skinning.global_onion_skinning_enabled = False
        restore_onion_skinning.set_animation_onion_state('walk', {5: True})
        canvas_sprite = FakeCanvasSprite(
            animated_sprite=FakeAnimatedSprite({
                'walk': [_two_by_one_frame(), _two_by_one_frame(), _two_by_one_frame()],
            }),
        )
        editor = SimpleNamespace(all_sprites=[canvas_sprite])

        FileIOManager(editor)._load_converted_sprite('walk.toml')

        assert restore_onion_skinning.get_animation_onion_state('walk') == {
            0: False,
            1: True,
            2: True,
        }
        assert restore_onion_skinning.is_global_onion_skinning_enabled() is True

    def test_no_canvas_sprite_loads_nothing(self):
        """Without a sprite that loads files, nothing happens."""
        editor = SimpleNamespace(all_sprites=[object()])

        FileIOManager(editor)._load_converted_sprite('sprite.toml')

    def test_sprite_without_animations_leaves_canvas_pixels_alone(self):
        """A loaded sprite with no animations transfers no pixels."""
        canvas_sprite = FakeCanvasSprite(animated_sprite=FakeAnimatedSprite({}))
        canvas_sprite.pixels = [(1, 2, 3, 255)]
        editor = SimpleNamespace(all_sprites=[canvas_sprite])

        FileIOManager(editor)._load_converted_sprite('sprite.toml')

        assert canvas_sprite.pixels == [(1, 2, 3, 255)]
        assert canvas_sprite.redraw_count == 2

    def test_animation_without_frames_leaves_canvas_pixels_alone(self):
        """An animation with no frames transfers no pixels."""
        canvas_sprite = FakeCanvasSprite(animated_sprite=FakeAnimatedSprite({'idle': []}))
        canvas_sprite.pixels = [(1, 2, 3, 255)]
        editor = SimpleNamespace(all_sprites=[canvas_sprite])

        FileIOManager(editor)._load_converted_sprite('sprite.toml')

        assert canvas_sprite.pixels == [(1, 2, 3, 255)]

    def test_nothing_loaded_leaves_canvas_pixels_alone(self):
        """A canvas whose load produced no animated sprite keeps its pixels."""
        canvas_sprite = FakeCanvasSprite(animated_sprite=None)
        canvas_sprite.pixels = [(1, 2, 3, 255)]
        editor = SimpleNamespace(all_sprites=[canvas_sprite])

        FileIOManager(editor)._load_converted_sprite('sprite.toml')

        assert canvas_sprite.pixels == [(1, 2, 3, 255)]
        assert canvas_sprite.redraw_count == 2

    def test_animated_sprite_without_animations_attribute_transfers_nothing(self):
        """A loaded object with no _animations attribute is not an animation source."""
        canvas_sprite = FakeCanvasSprite(animated_sprite=None)
        canvas_sprite.animated_sprite = SimpleNamespace()  # type: ignore[assignment]
        canvas_sprite.pixels = [(1, 2, 3, 255)]

        FileIOManager(SimpleNamespace())._transfer_loaded_sprite_pixels(canvas_sprite)  # type: ignore[arg-type]

        assert canvas_sprite.pixels == [(1, 2, 3, 255)]

    def test_canvas_without_an_animated_sprite_attribute_transfers_nothing(self):
        """A canvas sprite with no animated_sprite attribute has nothing to transfer."""
        canvas_sprite = SimpleNamespace(pixels=[(1, 2, 3, 255)])

        FileIOManager(SimpleNamespace())._transfer_loaded_sprite_pixels(canvas_sprite)  # type: ignore[arg-type]

        assert canvas_sprite.pixels == [(1, 2, 3, 255)]

    def test_load_error_is_logged_not_raised(self, caplog):
        """An error inside the canvas load is caught and logged."""

        class BrokenCanvasSprite(FakeCanvasSprite):
            def on_load_file_event(self, event: object) -> None:
                msg = 'cannot read'
                raise OSError(msg)

        editor = SimpleNamespace(all_sprites=[BrokenCanvasSprite(animated_sprite=None)])

        with caplog.at_level(logging.ERROR, logger='game.tools.bitmappy.file_io'):
            FileIOManager(editor)._load_converted_sprite('sprite.toml')

        assert any('Error loading converted sprite' in message for message in caplog.messages)


class TestApplyFramePixelsToCanvas:
    """Test _apply_frame_pixels_to_canvas."""

    def test_frame_without_an_image_changes_nothing(self):
        """A frame with no image has no pixels to transfer."""
        canvas_sprite = FakeCanvasSprite(animated_sprite=None)

        FileIOManager(SimpleNamespace())._apply_frame_pixels_to_canvas(
            canvas_sprite,  # type: ignore[arg-type]
            SimpleNamespace(image=None),  # type: ignore[arg-type]
        )

        assert canvas_sprite.pixels == []

    def test_three_component_colors_become_opaque_rgba(self):
        """A surface whose colors have no alpha component yields opaque RGBA pixels."""
        canvas_sprite = FakeCanvasSprite(animated_sprite=None)

        FileIOManager(SimpleNamespace())._apply_frame_pixels_to_canvas(
            canvas_sprite,  # type: ignore[arg-type]
            SimpleNamespace(image=RgbSurface(color=RgbColor((7, 8, 9)))),  # type: ignore[arg-type]
        )

        assert canvas_sprite.pixels == [(7, 8, 9, 255)]


class TestInitializeOnionSkinningErrors:
    """Errors while setting up onion skinning are logged, not raised."""

    def test_bad_frame_list_is_logged(self, caplog, restore_onion_skinning):
        """An animation whose frames have no length cannot be initialized."""
        loaded_sprite = SimpleNamespace(_animations={'idle': 5})

        with caplog.at_level(logging.ERROR, logger='game.tools.bitmappy.file_io'):
            FileIOManager(SimpleNamespace())._initialize_onion_skinning_for_sprite(loaded_sprite)  # type: ignore[arg-type]

        assert any('Failed to initialize onion skinning' in m for m in caplog.messages)
