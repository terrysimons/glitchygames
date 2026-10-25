"""The CRT power-on sequence: every game's canvas switches on like an analogue TV first.

Before control is handed to the game (``GameEngine._prepare_run``, so every game, Bitmappy
included), its canvas shows a CRT switching on: black, a bright dot in the centre, the dot
stretched into a line, the picture opening from the line, a warm-up flicker, then the
configured default background (glitchygames/backgrounds.py: the TV test pattern or the channel
3 screen). ``--crt-power-on`` chooses when it plays (``should_play``):

- ``auto`` (the default): when someone can see it and nothing is disturbed: not on SDL's dummy
  video driver (``--headless``, every test), and not before a replay, an audit, a rebaseline
  or a recording (events pumped before frame 0 would be input the game never saw);
- ``on``: always (refused with a replay or a recording); ``off``: never.

Rules it keeps: visual only, before the game's first scene exists, so it changes no game state,
random stream, frame clock or scene clock, and is never in a recording or screenshot. It uses
no randomness: the flicker is a fixed table. Events are taken only through the doors and
dropped, except that a key or button press skips the rest and a QUIT is handed back to the
game, which then quits.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any

import pygame

from glitchygames.opacity import make_opaque

if TYPE_CHECKING:
    from collections.abc import Mapping

# The SDL video driver nobody can see (--headless; every test)
INVISIBLE_VIDEO_DRIVER = 'dummy'
# Options whose run must not have anything happen before frame 0
RUN_RECORDED_OR_REPLAYED_OPTIONS = ('replay_trace', 'record_trace', 'audit', 'rebaseline')


class CrtPowerOnMode(enum.StrEnum):
    """When the power-on sequence plays (``--crt-power-on``)."""

    AUTO = 'auto'
    ON = 'on'
    OFF = 'off'


def should_play(*, mode: CrtPowerOnMode, video_driver: str, options: Mapping[str, Any]) -> bool:
    """Return whether the power-on sequence plays for this run.

    Args:
        mode: ``--crt-power-on``.
        video_driver: SDL's video driver (``pygame.display.get_driver()``).
        options: The run's options.

    Returns:
        True to play it.

    """
    if mode is CrtPowerOnMode.ON:
        return True
    if mode is CrtPowerOnMode.OFF:
        return False
    if video_driver == INVISIBLE_VIDEO_DRIVER:
        return False
    return not any(options.get(name) for name in RUN_RECORDED_OR_REPLAYED_OPTIONS)


# The sequence's stages, as fractions of its length (each stage ends where the next starts)
DOT_STAGE_START = 0.08
LINE_STAGE_START = 0.18
OPEN_STAGE_START = 0.30
WARM_UP_STAGE_START = 0.50
SETTLED_STAGE_START = 0.90
# The electron beam's colour: a slightly blue white, as a phosphor glows when first hit
BEAM_COLOR = (235, 240, 255)
BLACK = (0, 0, 0)
# The dot's largest radius, as a fraction of the screen's shorter side (at least one pixel)
DOT_RADIUS_FRACTION = 0.03
# The line's thickness, as a fraction of the screen's height (at least one pixel)
LINE_THICKNESS_FRACTION = 0.02
# How much brighter the picture is while it opens (added to each channel, fading out)
OPENING_GLOW = 60
# The warm-up's brightness, one factor per equal step: an overshoot, then sags and recoveries
# as the tube warms (a fixed table: the sequence uses no randomness)
WARM_UP_BRIGHTNESS = (1.35, 1.25, 0.70, 1.10, 0.85, 1.05, 0.92, 1.03, 0.97, 1.01)
# The warm-up steps whose picture rolls vertically, and by how much of the height
ROLL_STEPS = frozenset({2, 3})
ROLL_FRACTION = 0.12
# The warm-up steps with a colour wobble (degaussing), and the tint they multiply by
WOBBLE_STEPS = frozenset({4, 6})
WOBBLE_TINT = (255, 215, 235)
# Scanlines: every other row darkened by this factor at the warm-up's start, fading to none
SCANLINE_DARKENING = 0.65
# How much brighter than a channel's full value a brightness above 1 adds, per unit
BRIGHTENING_SCALE = 200


def _stage_fraction(*, progress: float, start: float, end: float) -> float:
    """Return how far ``progress`` is through the stage from ``start`` to ``end`` (0 to 1).

    Returns:
        The fraction.

    """
    return min(1.0, max(0.0, (progress - start) / (end - start)))


def _ease_out(fraction: float) -> float:
    """Return a quadratic ease-out of ``fraction``: fast at first, settling at the end.

    Returns:
        The eased fraction.

    """
    return 1.0 - (1.0 - fraction) ** 2


def _set_brightness(*, surface: pygame.Surface, brightness: float) -> None:
    """Scale a surface's brightness: darken below 1, brighten (towards white) above 1."""
    if brightness < 1.0:
        level = round(255 * brightness)
        surface.fill((level, level, level), special_flags=pygame.BLEND_RGB_MULT)
    elif brightness > 1.0:
        added = round(BRIGHTENING_SCALE * (brightness - 1.0))
        surface.fill((added, added, added), special_flags=pygame.BLEND_RGB_ADD)


def _draw_dot(*, surface: pygame.Surface, fraction: float) -> None:
    width, height = surface.get_size()
    largest = max(1, round(min(width, height) * DOT_RADIUS_FRACTION))
    radius = max(1, round(largest * _ease_out(fraction)))
    pygame.draw.circle(surface, BEAM_COLOR, (width // 2, height // 2), radius)


def _line_thickness(*, height: int) -> int:
    return max(1, round(height * LINE_THICKNESS_FRACTION))


def _draw_line(*, surface: pygame.Surface, fraction: float) -> None:
    width, height = surface.get_size()
    thickness = _line_thickness(height=height)
    length = max(1, round(width * _ease_out(fraction)))
    line = pygame.Rect(0, 0, length, thickness)
    line.center = (width // 2, height // 2)
    surface.fill(BEAM_COLOR, line)


def _draw_opening(*, surface: pygame.Surface, picture: pygame.Surface, fraction: float) -> None:
    """The picture squashed into a band that opens from the line to the full height."""
    width, height = surface.get_size()
    thickness = _line_thickness(height=height)
    band_height = max(thickness, round(height * _ease_out(fraction)))
    band = pygame.transform.smoothscale(picture, (width, band_height))
    _set_brightness(surface=band, brightness=1.0 + OPENING_GLOW * (1.0 - fraction) / 255)
    top = (height - band_height) // 2
    surface.blit(band, (0, top))
    # The beam is brightest where it is still sweeping open: the band's edges
    surface.fill(BEAM_COLOR, pygame.Rect(0, top, width, 1))
    surface.fill(BEAM_COLOR, pygame.Rect(0, top + band_height - 1, width, 1))


def _draw_warm_up(*, surface: pygame.Surface, picture: pygame.Surface, fraction: float) -> None:
    """The full picture flickering, rolling and wobbling as the tube warms up."""
    width, height = surface.get_size()
    step = min(len(WARM_UP_BRIGHTNESS) - 1, int(fraction * len(WARM_UP_BRIGHTNESS)))
    offset = round(height * ROLL_FRACTION) if step in ROLL_STEPS else 0
    surface.blit(picture, (0, -offset))
    if offset:
        surface.blit(picture, (0, height - offset))
    _set_brightness(surface=surface, brightness=WARM_UP_BRIGHTNESS[step])
    if step in WOBBLE_STEPS:
        surface.fill(WOBBLE_TINT, special_flags=pygame.BLEND_RGB_MULT)
    darkening = SCANLINE_DARKENING + (1.0 - SCANLINE_DARKENING) * fraction
    level = round(255 * darkening)
    for row in range(1, height, 2):
        surface.fill(
            (level, level, level),
            pygame.Rect(0, row, width, 1),
            special_flags=pygame.BLEND_RGB_MULT,
        )


def draw_power_on(*, surface: pygame.Surface, picture: pygame.Surface, progress: float) -> None:
    """Draw the moment ``progress`` (0 to 1) of the power-on sequence onto ``surface``.

    Args:
        surface: Where to draw (the game's canvas), covered entirely.
        picture: The settled picture, at the surface's size (the default background pattern,
            ``backgrounds.background_pattern_surface``); only read.
        progress: How far through the sequence, from 0 (off) to 1 (settled).

    """
    surface.fill(BLACK)
    if progress >= SETTLED_STAGE_START:
        surface.blit(picture, (0, 0))
    elif progress >= WARM_UP_STAGE_START:
        _draw_warm_up(
            surface=surface,
            picture=picture,
            fraction=_stage_fraction(
                progress=progress, start=WARM_UP_STAGE_START, end=SETTLED_STAGE_START
            ),
        )
    elif progress >= OPEN_STAGE_START:
        _draw_opening(
            surface=surface,
            picture=picture,
            fraction=_stage_fraction(
                progress=progress, start=OPEN_STAGE_START, end=WARM_UP_STAGE_START
            ),
        )
    elif progress >= LINE_STAGE_START:
        _draw_line(
            surface=surface,
            fraction=_stage_fraction(
                progress=progress, start=LINE_STAGE_START, end=OPEN_STAGE_START
            ),
        )
    elif progress >= DOT_STAGE_START:
        _draw_dot(
            surface=surface,
            fraction=_stage_fraction(
                progress=progress, start=DOT_STAGE_START, end=LINE_STAGE_START
            ),
        )
    make_opaque(surface=surface)
