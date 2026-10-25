"""Tests for swatches, recolouring sprites by palette swap, on real pygame (the dummy driver)."""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

from glitchygames.examples.drawing_fire.swatches import (
    RecoloredFrames,
    Scheme,
    SwatchError,
    SwatchPart,
    SwatchSet,
    load_frames,
    load_swatch_sets,
    recolor_surface,
    shade_map,
)

SOLDIER_PATH = (
    Path(__file__).parents[3]
    / 'glitchygames'
    / 'examples'
    / 'drawing_fire'
    / 'sprites'
    / 'soldier.toml'
)

OUTLINE = (58, 58, 64)
HELMET_BASE = (210, 60, 60)
HELMET_SHADOW = (140, 40, 40)  # 2/3 of the base
UNIFORM_BASE = (90, 130, 200)
PENCIL_YELLOW = (242, 194, 48)
GRAPHITE_GREY = (125, 127, 133)
UNIFORM_GREEN = (40, 120, 60)

TEST_TOML = """\
[sprite]
name = "tiny"

[colors]
"█" = { red = 255, green = 0, blue = 255 }
"o" = { red = 58, green = 58, blue = 64 }
"h" = { red = 210, green = 60, blue = 60 }
"H" = { red = 140, green = 40, blue = 40 }
"u" = { red = 90, green = 130, blue = 200 }

[swatches.livery.helmet]
colors = ["h", "H"]
role = "primary"

[swatches.livery.uniform]
colors = ["u"]
role = "secondary"

[swatches.livery.badge]
colors = ["o"]
"""


@pytest.fixture(autouse=True)
def pygame_ready():
    """Real pygame, initialized (the dummy driver)."""
    if not pygame.get_init():
        pygame.init()


@pytest.fixture
def swatch_set():
    """A livery: a helmet (primary, with a shadow) and a uniform (secondary)."""
    return SwatchSet(
        name='livery',
        parts=(
            SwatchPart(name='helmet', colors=(HELMET_BASE, HELMET_SHADOW), role='primary'),
            SwatchPart(name='uniform', colors=(UNIFORM_BASE,), role='secondary'),
        ),
    )


@pytest.fixture
def surface():
    """A 4x1 surface: helmet, helmet shadow, uniform, outline."""
    drawn = pygame.Surface((4, 1))
    for x, color in enumerate((HELMET_BASE, HELMET_SHADOW, UNIFORM_BASE, OUTLINE)):
        drawn.set_at((x, 0), color)
    return drawn


def write_toml(*, directory: Path, text: str) -> Path:
    """Write a sprite file.

    Returns:
        The file's path.

    """
    path = directory / 'tiny.toml'
    path.write_text(text, encoding='utf-8')
    return path


def pixels_of(surface: pygame.Surface) -> list[tuple[int, int, int]]:
    """Read a one-row surface's RGB pixels.

    Returns:
        The pixels' colours.

    """
    return [tuple(surface.get_at((x, 0)))[:3] for x in range(surface.get_width())]


def test_a_scheme_recolors_each_part_by_its_role(swatch_set, surface):
    """Helmet pixels take the primary colour and uniform pixels the secondary."""
    scheme = Scheme(primary=PENCIL_YELLOW, secondary=UNIFORM_GREEN)
    recolored = recolor_surface(surface=surface, swatch_set=swatch_set, scheme=scheme)
    pixels = pixels_of(recolored)
    assert pixels[0] == PENCIL_YELLOW
    assert pixels[2] == UNIFORM_GREEN
    assert pixels_of(surface)[0] == HELMET_BASE  # the original is left as drawn


def test_shadows_keep_their_brightness_ratio(swatch_set, surface):
    """The helmet's shadow, 2/3 of its base, is 2/3 of the new primary."""
    recolored = recolor_surface(
        surface=surface,
        swatch_set=swatch_set,
        scheme=Scheme(primary=PENCIL_YELLOW),
    )
    expected = tuple(round(channel * 2 / 3) for channel in PENCIL_YELLOW)
    shadow = pixels_of(recolored)[1]
    for actual_channel, expected_channel in zip(shadow, expected, strict=True):
        assert abs(actual_channel - expected_channel) <= 1


def test_shade_map_clamps_and_handles_a_black_channel():
    """Channels clamp to 255; a base channel of 0 has no ratio, so the shade takes the new one."""
    part = SwatchPart(name='bright', colors=((100, 0, 100), (200, 50, 100)), role=None)
    mapping = shade_map(part=part, color=(250, 80, 250))
    assert mapping[100, 0, 100] == (250, 80, 250)
    assert mapping[200, 50, 100] == (255, 80, 250)


def test_shade_map_ignores_a_shade_equal_to_the_base():
    """A shade of the same colour as the base adds nothing, so the base wins."""
    part = SwatchPart(name='plain', colors=((10, 10, 10), (10, 10, 10)), role=None)
    assert shade_map(part=part, color=(20, 20, 20)) == {(10, 10, 10): (20, 20, 20)}


def test_a_part_colour_wins_over_its_role(swatch_set, surface):
    """A scheme's colour for a named part beats the role's colour."""
    scheme = Scheme(primary=PENCIL_YELLOW, secondary=UNIFORM_GREEN, parts={'helmet': GRAPHITE_GREY})
    recolored = recolor_surface(surface=surface, swatch_set=swatch_set, scheme=scheme)
    pixels = pixels_of(recolored)
    assert pixels[0] == GRAPHITE_GREY
    assert pixels[2] == UNIFORM_GREEN


def test_color_for_finds_a_part_by_name_then_role_then_nothing():
    """A part's own colour, else its role's, else None (also for a part with no role)."""
    scheme = Scheme(primary=PENCIL_YELLOW, parts={'visor': GRAPHITE_GREY})
    assert scheme.color_for(SwatchPart(name='visor', colors=(OUTLINE,), role='primary')) == (
        GRAPHITE_GREY
    )
    assert scheme.color_for(SwatchPart(name='helmet', colors=(OUTLINE,), role='primary')) == (
        PENCIL_YELLOW
    )
    assert scheme.color_for(SwatchPart(name='boots', colors=(OUTLINE,), role='secondary')) is None
    assert scheme.color_for(SwatchPart(name='belt', colors=(OUTLINE,), role=None)) is None


def test_unlisted_colours_and_transparency_are_untouched(swatch_set):
    """Colours outside the swatches, the colorkey and alpha stay exactly as drawn."""
    keyed = pygame.Surface((3, 1))
    keyed.set_colorkey((255, 0, 255))
    keyed.set_at((0, 0), OUTLINE)
    keyed.set_at((1, 0), (255, 0, 255))
    keyed.set_at((2, 0), HELMET_BASE)
    scheme = Scheme(primary=PENCIL_YELLOW)
    recolored = recolor_surface(surface=keyed, swatch_set=swatch_set, scheme=scheme)
    assert recolored.get_colorkey() == keyed.get_colorkey()
    assert pixels_of(recolored) == [OUTLINE, (255, 0, 255), PENCIL_YELLOW]

    translucent = pygame.Surface((3, 1), pygame.SRCALPHA)
    translucent.set_at((0, 0), (*OUTLINE, 255))
    translucent.set_at((1, 0), (*HELMET_BASE, 0))  # fully transparent: left alone
    translucent.set_at((2, 0), (*HELMET_BASE, 128))
    recolored = recolor_surface(surface=translucent, swatch_set=swatch_set, scheme=scheme)
    assert tuple(recolored.get_at((0, 0))) == (*OUTLINE, 255)
    assert tuple(recolored.get_at((1, 0))) == (*HELMET_BASE, 0)
    assert tuple(recolored.get_at((2, 0))) == (*PENCIL_YELLOW, 128)


def test_parts_the_scheme_gives_no_colour_stay_as_drawn(swatch_set, surface):
    """An empty scheme recolours nothing, but still gives a new surface."""
    recolored = recolor_surface(surface=surface, swatch_set=swatch_set, scheme=Scheme())
    assert recolored is not surface
    assert pixels_of(recolored) == pixels_of(surface)


def test_a_scheme_hashes_by_its_colours():
    """Schemes built from equal mappings are equal and hash the same; Scheme() works."""
    first = Scheme(primary=PENCIL_YELLOW, parts={'helmet': OUTLINE, 'boots': GRAPHITE_GREY})
    second = Scheme(primary=PENCIL_YELLOW, parts={'boots': GRAPHITE_GREY, 'helmet': OUTLINE})
    assert first == second
    assert hash(first) == hash(second)
    assert first != Scheme(primary=PENCIL_YELLOW)
    assert Scheme() == Scheme(parts={})
    assert len({first, second, Scheme()}) == 2


def test_each_scheme_is_built_once(swatch_set, surface):
    """frames_for gives the same surfaces (identity) for the same scheme, new ones for another."""
    recolored_frames = RecoloredFrames(frames={'stand': [surface, surface]}, swatch_set=swatch_set)
    yellow = Scheme(primary=PENCIL_YELLOW)
    first = recolored_frames.frames_for(yellow)
    again = recolored_frames.frames_for(Scheme(primary=PENCIL_YELLOW))
    assert first is again
    assert len(first['stand']) == 2
    assert first['stand'][0] is again['stand'][0]
    grey = recolored_frames.frames_for(Scheme(primary=GRAPHITE_GREY))
    assert pixels_of(grey['stand'][0])[0] == GRAPHITE_GREY
    assert pixels_of(first['stand'][0])[0] == PENCIL_YELLOW


def test_swatch_sets_load_with_colours_in_the_files_order(tmp_path):
    """Each part has the RGB of its listed characters, in order, and its role (or None)."""
    swatch_sets = load_swatch_sets(path=write_toml(directory=tmp_path, text=TEST_TOML))
    livery = swatch_sets['livery']
    assert livery.name == 'livery'
    parts = {part.name: part for part in livery.parts}
    assert parts['helmet'].colors == (HELMET_BASE, HELMET_SHADOW)
    assert parts['helmet'].role == 'primary'
    assert parts['uniform'].role == 'secondary'
    assert parts['badge'].role is None


def test_a_file_without_swatches_has_no_sets(tmp_path):
    """No [swatches] table is no sets."""
    text = TEST_TOML.split('[swatches', maxsplit=1)[0]
    assert load_swatch_sets(path=write_toml(directory=tmp_path, text=text)) == {}


def test_an_unknown_palette_character_is_an_error(tmp_path):
    """The error names the file and the part."""
    text = TEST_TOML.replace('colors = ["u"]', 'colors = ["u", "?"]')
    path = write_toml(directory=tmp_path, text=text)
    with pytest.raises(SwatchError, match=r'tiny\.toml.*uniform.*\?'):
        load_swatch_sets(path=path)


def test_a_part_with_no_colours_is_an_error(tmp_path):
    """An empty colours list, or none at all, names the file and the part."""
    path = write_toml(directory=tmp_path, text=TEST_TOML.replace('colors = ["u"]', 'colors = []'))
    with pytest.raises(SwatchError, match=r'tiny\.toml.*uniform.*no colours'):
        load_swatch_sets(path=path)
    path = write_toml(directory=tmp_path, text=TEST_TOML.replace('colors = ["u"]\n', ''))
    with pytest.raises(SwatchError, match=r'tiny\.toml.*uniform.*no colours'):
        load_swatch_sets(path=path)


def test_a_character_in_two_parts_of_one_set_is_an_error(tmp_path):
    """The error names the file, the set and both parts."""
    path = write_toml(
        directory=tmp_path,
        text=TEST_TOML.replace('colors = ["u"]', 'colors = ["u", "h"]'),
    )
    with pytest.raises(SwatchError, match=r'tiny\.toml.*livery.*\'h\''):
        load_swatch_sets(path=path)


def test_the_soldier_sprite_has_a_livery():
    """soldier.toml has a livery with a primary helmet and a secondary uniform, each shaded."""
    livery = load_swatch_sets(path=SOLDIER_PATH)['livery']
    parts = {part.name: part for part in livery.parts}
    assert set(parts) == {'helmet', 'uniform'}
    assert parts['helmet'].role == 'primary'
    assert parts['uniform'].role == 'secondary'
    assert len(parts['helmet'].colors) == 2
    assert len(parts['uniform'].colors) >= 2


def test_load_frames_gives_each_animations_surfaces():
    """The soldier has stand, a two-frame walk and down, drawn at one size."""
    frames = load_frames(path=SOLDIER_PATH)
    assert set(frames) == {'stand', 'walk', 'down'}
    assert len(frames['stand']) == 1
    assert len(frames['walk']) == 2
    assert len(frames['down']) == 1
    sizes = {frame.get_size() for animation in frames.values() for frame in animation}
    assert len(sizes) == 1
    assert all(isinstance(frame, pygame.Surface) for frame in frames['walk'])
    # the soldier's corner is paper: transparent, not the file's magenta key
    assert frames['stand'][0].get_at((0, 0)).a == 0
    assert frames['stand'][0].get_at((0, 21)).a == 0


def test_both_liveries_recolor_the_soldier():
    """Pencil yellow and graphite grey helmets differ, and the outline stays put."""
    livery = load_swatch_sets(path=SOLDIER_PATH)['livery']
    recolored_frames = RecoloredFrames(frames=load_frames(path=SOLDIER_PATH), swatch_set=livery)
    yellow = recolored_frames.frames_for(Scheme(primary=PENCIL_YELLOW, secondary=PENCIL_YELLOW))
    grey = recolored_frames.frames_for(Scheme(primary=GRAPHITE_GREY, secondary=GRAPHITE_GREY))

    def colors_in(surface):
        return {
            tuple(surface.get_at((x, y)))[:3]
            for x in range(surface.get_width())
            for y in range(surface.get_height())
        }

    assert PENCIL_YELLOW in colors_in(yellow['stand'][0])
    assert GRAPHITE_GREY in colors_in(grey['stand'][0])
    assert PENCIL_YELLOW not in colors_in(grey['stand'][0])
    assert OUTLINE in colors_in(yellow['stand'][0])
    assert HELMET_BASE not in colors_in(yellow['walk'][1])
