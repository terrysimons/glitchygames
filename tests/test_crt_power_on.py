"""The CRT power-on sequence before every game (glitchygames/crt_power_on.py)."""

from __future__ import annotations

import pygame
import pytest

from glitchygames.backgrounds import (
    active_default_background_pattern,
    background_pattern_surface,
    paint_default_background,
)
from glitchygames.crt_power_on import (
    DOT_STAGE_START,
    LINE_STAGE_START,
    OPEN_STAGE_START,
    WARM_UP_STAGE_START,
    CrtPowerOnMode,
    draw_power_on,
    should_play,
)


@pytest.mark.parametrize(
    ('mode', 'video_driver', 'options', 'plays'),
    [
        # Someone is watching a live run
        (CrtPowerOnMode.AUTO, 'cocoa', {}, True),
        # Nobody sees SDL's dummy driver: --headless, and every test
        (CrtPowerOnMode.AUTO, 'dummy', {}, False),
        # Before frame 0 of a replay, an audit, a rebaseline or a recording: never
        (CrtPowerOnMode.AUTO, 'cocoa', {'replay_trace': 'run.jsonl.gz'}, False),
        (CrtPowerOnMode.AUTO, 'cocoa', {'record_trace': 'run.jsonl.gz'}, False),
        (CrtPowerOnMode.AUTO, 'cocoa', {'audit': True}, False),
        (CrtPowerOnMode.AUTO, 'cocoa', {'rebaseline': 'new.jsonl.gz'}, False),
        # Options left at their defaults (None, False) are not set
        (CrtPowerOnMode.AUTO, 'cocoa', {'replay_trace': None, 'audit': False}, True),
        (CrtPowerOnMode.OFF, 'cocoa', {}, False),
        # The sequence's own tests force it on the dummy driver
        (CrtPowerOnMode.ON, 'dummy', {}, True),
    ],
)
def test_when_the_sequence_plays(mode, video_driver, options, plays):
    """Auto plays only where someone watches and nothing is recorded or replayed."""
    assert should_play(mode=mode, video_driver=video_driver, options=options) is plays


SIZE = (160, 120)


def settled_picture(*, size: tuple[int, int] = SIZE) -> pygame.Surface:
    """Return the background the sequence settles on (the engine's default pattern)."""
    return background_pattern_surface(pattern=active_default_background_pattern(), size=size)


def drawn(*, progress: float, size: tuple[int, int] = SIZE) -> pygame.Surface:
    """Return a surface showing the sequence at ``progress``."""
    surface = pygame.Surface(size)
    surface.fill((90, 10, 200))  # anything the drawing must cover
    draw_power_on(surface=surface, picture=settled_picture(size=size), progress=progress)
    return surface


def is_bright(color: pygame.Color) -> bool:
    """Whether a pixel is near white (the beam)."""
    return min(color.r, color.g, color.b) > 200


def is_black(color: pygame.Color) -> bool:
    """Whether a pixel is black (the tube showing nothing there)."""
    return max(color.r, color.g, color.b) == 0


def test_it_starts_black():
    """The tube is off: every pixel black."""
    surface = drawn(progress=0.0)

    assert pygame.transform.average_color(surface)[:3] == (0, 0, 0)


def test_the_beam_first_shows_as_a_dot_in_the_centre():
    """Before the beam deflects it lights one spot in the middle."""
    middle_of_dot = (DOT_STAGE_START + LINE_STAGE_START) / 2
    surface = drawn(progress=middle_of_dot)

    assert is_bright(surface.get_at((SIZE[0] // 2, SIZE[1] // 2)))
    assert is_black(surface.get_at((0, 0)))
    assert is_black(surface.get_at((SIZE[0] // 4, SIZE[1] // 2)))


def test_the_dot_stretches_into_a_line_across_the_screen():
    """The horizontal sweep comes first: a thin bright line, nothing above it."""
    end_of_line = OPEN_STAGE_START - 0.001
    surface = drawn(progress=end_of_line)
    centre_row = SIZE[1] // 2

    assert is_bright(surface.get_at((SIZE[0] // 6, centre_row)))
    assert is_bright(surface.get_at((SIZE[0] * 5 // 6, centre_row)))
    assert is_black(surface.get_at((SIZE[0] // 2, centre_row - SIZE[1] // 10)))


def test_the_picture_opens_from_the_line():
    """Half way through opening: a band of picture in the middle, black above and below."""
    middle_of_open = (OPEN_STAGE_START + WARM_UP_STAGE_START) / 2
    surface = drawn(progress=middle_of_open)

    assert not is_black(surface.get_at((SIZE[0] // 4, SIZE[1] // 2)))
    assert is_black(surface.get_at((SIZE[0] // 4, 0)))
    assert is_black(surface.get_at((SIZE[0] // 4, SIZE[1] - 1)))


def test_the_warm_up_flickers_around_the_picture():
    """The whole picture shows, but not yet at its settled brightness."""
    settled = pygame.transform.average_color(drawn(progress=1.0))
    warming_up = [
        pygame.transform.average_color(drawn(progress=progress))
        for progress in (0.52, 0.56, 0.62, 0.70, 0.80)
    ]

    assert all(color[:3] != (0, 0, 0) for color in warming_up)
    assert any(color[:3] != settled[:3] for color in warming_up)


def test_it_settles_on_exactly_the_default_background():
    """The hand-over frame is the picture the engine painted before this sequence existed."""
    expected = pygame.Surface(SIZE)
    paint_default_background(surface=expected)

    assert pygame.image.tobytes(drawn(progress=1.0), 'RGB') == pygame.image.tobytes(expected, 'RGB')


@pytest.mark.parametrize('size', [(1, 1), (7, 5), (2, 300)])
@pytest.mark.parametrize('progress', [0.0, 0.1, 0.2, 0.35, 0.45, 0.6, 0.85, 0.95, 1.0])
def test_every_moment_draws_at_any_size(size, progress):
    """Tiny or odd windows draw without error (no zero-sized scaling)."""
    drawn(progress=progress, size=size)


def test_drawing_never_changes_the_picture():
    """The picture is the shared, cached pattern surface: it is only read."""
    picture = settled_picture()
    before = pygame.image.tobytes(picture, 'RGB')

    for progress in (0.1, 0.25, 0.4, 0.6, 1.0):
        draw_power_on(surface=pygame.Surface(SIZE), picture=picture, progress=progress)

    assert pygame.image.tobytes(picture, 'RGB') == before
